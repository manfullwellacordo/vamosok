from fastapi import FastAPI, WebSocket, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
from sqlalchemy import func, select
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import json
from typing import List, Optional
import asyncio
import sys
import multiprocessing
from aiocache import Cache
from cachetools import TTLCache
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add file handler
file_handler = RotatingFileHandler('app.log', maxBytes=10485760, backupCount=5)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Initialize cache
metrics_cache = TTLCache(maxsize=100, ttl=300)  # Cache for 5 minutes
cache = Cache(Cache.MEMORY)

# Database configuration
DATABASE_URL = "sqlite+aiosqlite:///./sql_app.db"
engine = create_async_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30
    },
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=0,
    echo=True
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# FastAPI app initialization
app = FastAPI(title="Dashboard API")

# Add GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket connection. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Remaining connections: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {str(e)}")
                await self.disconnect(connection)

manager = ConnectionManager()

@asynccontextmanager
async def get_db():
    async with async_session() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()

async def update_metrics():
    while True:
        try:
            async with async_session() as session:
                # Fetch and process metrics
                query = select(Metrics).order_by(Metrics.date.desc()).limit(100)
                result = await session.execute(query)
                metrics = result.scalars().all()
                
                # Update cache
                metrics_data = [metric.to_dict() for metric in metrics]
                metrics_cache.update({
                    'latest_metrics': metrics_data
                })
                
                # Broadcast updates
                await manager.broadcast(json.dumps({
                    'type': 'metrics_update',
                    'data': metrics_data
                }))
                
        except Exception as e:
            logger.error(f"Error updating metrics: {str(e)}")
        
        await asyncio.sleep(300)  # Update every 5 minutes

@app.on_event("startup")
async def startup_event():
    try:
        # Test database connection
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
        
        # Start background tasks
        asyncio.create_task(update_metrics())
        logger.info("Background tasks started")
        
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    try:
        await engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}")

@app.get("/api/metrics")
async def get_metrics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Check cache first
        cache_key = f"metrics_{start_date}_{end_date}"
        cached_data = await cache.get(cache_key)
        if cached_data:
            return JSONResponse(content=cached_data)
        
        query = select(Metrics)
        
        if start_date:
            query = query.filter(Metrics.date >= start_date)
        if end_date:
            query = query.filter(Metrics.date <= end_date)
            
        result = await db.execute(query.options(selectinload(Metrics.alerts)))
        metrics = result.scalars().all()
        
        response_data = {
            "metrics": [metric.to_dict() for metric in metrics],
            "count": len(metrics),
            "timestamp": datetime.now().isoformat()
        }
        
        # Cache the results
        await cache.set(cache_key, response_data, ttl=300)
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"Error fetching metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message received: {data}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        manager.disconnect(websocket)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "path": str(request.url),
            "timestamp": datetime.now().isoformat()
        }
    )

if __name__ == "__main__":
    if sys.platform == 'win32':
        multiprocessing.set_start_method('spawn')
    
    import uvicorn
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8001,
        workers=1,
        loop="asyncio",
        reload=True
    )
    server = uvicorn.Server(config)
    server.run()