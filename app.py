from fastapi import FastAPI, WebSocket, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.wsgi import WSGIMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, html, dcc
import dash_bootstrap_components as dbc
from pathlib import Path
import os
from dotenv import load_dotenv
from health_check import HealthCheck
import logging
from sqlalchemy.sql import text

from models import Contract, DailyMetrics, Alert, init_db
from websocket_manager import manager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Dashboard de Análise de Contratos")

# Setup directories
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Create directories if they don't exist
TEMPLATES_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Initialize Dash app
dash_app = Dash(
    __name__,
    requests_pathname_prefix="/dash/",
    assets_folder=str(STATIC_DIR)
)

# Define the Dash layout
dash_app.layout = html.Div([
    html.H1("Dashboard de Análise de Contratos"),
    html.Div([
        html.Div([
            html.H3("Métricas Principais"),
            html.Div(id="metrics-container")
        ]),
        html.Div([
            html.H3("Gráficos"),
            dcc.Graph(id="status-chart"),
            dcc.Graph(id="resolution-chart")
        ])
    ])
])

# Mount Dash app
app.mount("/dash", WSGIMiddleware(dash_app.server))

# Database
DB_PATH = os.getenv("DB_PATH", "relatorio_dashboard.db")
engine = init_db(f"sqlite:///{DB_PATH}")

# Database session dependency
def get_db():
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Startup event
@app.on_event("startup")
async def startup_event():
    """Executa verificações do sistema durante a inicialização"""
    try:
        logger.info("Starting system initialization...")
        
        # Verificar diretórios necessários
        for directory in [TEMPLATES_DIR, STATIC_DIR]:
            if not directory.exists():
                logger.warning(f"Creating missing directory: {directory}")
                directory.mkdir(parents=True, exist_ok=True)

        # Executar verificações de saúde do sistema
        checker = HealthCheck()
        check_result = checker.run_all_checks()
        
        # Registrar métricas de performance
        for metric, value in checker.performance_metrics.items():
            logger.info(f"Performance metric - {metric}: {value:.2f}")
        
        # Registrar avisos
        for warning in checker.warnings:
            logger.warning(warning)
        
        # Se houver erros críticos, não permitir que o servidor inicie
        if not check_result:
            for error in checker.errors:
                logger.error(f"Critical error: {error}")
            raise SystemExit("System cannot start due to critical errors")
        
        # Inicializar WebSocket manager
        await manager.startup()
        logger.info("WebSocket manager initialized")
        
        # Verificar conexão com banco de dados
        try:
            db = next(get_db())
            db.execute(text("SELECT 1"))
            logger.info("Database connection verified")
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            raise SystemExit("Cannot establish database connection")
        finally:
            db.close()
        
        logger.info("System initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise SystemExit(f"Error during startup: {str(e)}")

# FastAPI routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )

@app.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str):
    await manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(
                {"message": f"You wrote: {data}"}, websocket
            )
    except:
        manager.disconnect(websocket, channel)

@app.get("/api/metrics")
async def get_metrics(
    db: Session = Depends(get_db),
    grupo: str = None,
    collaborator: str = None,
    status: str = None,
    data: str = None
):
    try:
        # Get current date for filtering
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        # Base query for contracts
        query = db.query(Contract)

        # Apply filters
        if grupo:
            # Filter by group (JULIO or LEANDRO)
            if grupo == "JULIO":
                query = query.filter(Contract.contract_number.like("JULIO-%"))
            elif grupo == "LEANDRO":
                query = query.filter(Contract.contract_number.like("LEANDRO-%"))
        
        if collaborator:
            query = query.filter(Contract.collaborator == collaborator)
            
        if status:
            query = query.filter(Contract.status == status)
            
        if data:
            filter_date = datetime.strptime(data, "%Y-%m-%d").date()
            query = query.filter(
                func.date(Contract.created_at) == filter_date
            )

        # Get metrics by collaborator
        collaborator_metrics = {}
        collaborators = query.with_entities(Contract.collaborator).distinct().all()
        
        for (collaborator,) in collaborators:
            # Get contracts for this collaborator
            collaborator_contracts = query.filter(Contract.collaborator == collaborator).all()
            
            # Determine group based on contract numbers
            julio_contracts = sum(1 for c in collaborator_contracts if "JULIO-" in c.contract_number)
            leandro_contracts = sum(1 for c in collaborator_contracts if "LEANDRO-" in c.contract_number)
            
            # Assign group based on majority of contracts
            grupo = "JULIO" if julio_contracts > leandro_contracts else "LEANDRO"
            
            # Status counts for this collaborator
            status_counts = {}
            for status in ['verified', 'analysis', 'approved', 'pending', 'paid', 'seized', 'priority', 'high_priority', 'cancelled', 'other']:
                count = query.filter(
                    Contract.collaborator == collaborator,
                    Contract.status == status
                ).count()
                status_counts[status] = count
            
            # Average resolution time
            avg_resolution = db.query(func.avg(Contract.resolution_time)).filter(
                Contract.collaborator == collaborator,
                Contract.resolution_time.isnot(None)
            ).scalar() or 0
            
            # Contracts completed today
            completed_today = query.filter(
                Contract.collaborator == collaborator,
                Contract.status == 'verified',
                Contract.updated_at >= today_start,
                Contract.updated_at <= today_end
            ).count()
            
            collaborator_metrics[collaborator] = {
                "grupo": grupo,
                "status_counts": status_counts,
                "avg_resolution_time": round(avg_resolution, 2),
                "completed_today": completed_today,
                "total_contracts": sum(status_counts.values())
            }

        # Overall metrics
        total_contracts = query.count()
        total_verified = query.filter(Contract.status == 'verified').count()
        total_analysis = query.filter(Contract.status == 'analysis').count()
        total_approved = query.filter(Contract.status == 'approved').count()
        total_pending = query.filter(Contract.status == 'pending').count()
        total_paid = query.filter(Contract.status == 'paid').count()
        total_seized = query.filter(Contract.status == 'seized').count()
        total_priority = query.filter(Contract.status == 'priority').count()
        total_high_priority = query.filter(Contract.status == 'high_priority').count()
        total_cancelled = query.filter(Contract.status == 'cancelled').count()
        total_other = query.filter(Contract.status == 'other').count()

        return {
            "collaborator_metrics": collaborator_metrics,
            "total_metrics": {
                "total_contracts": total_contracts,
                "total_verified": total_verified,
                "total_analysis": total_analysis,
                "total_approved": total_approved,
                "total_pending": total_pending,
                "total_paid": total_paid,
                "total_seized": total_seized,
                "total_priority": total_priority,
                "total_high_priority": total_high_priority,
                "total_cancelled": total_cancelled,
                "total_other": total_other
            },
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"Erro ao obter métricas: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts")
async def get_alerts(db: Session = Depends(get_db)):
    try:
        # Get active alerts
        alerts = db.query(Alert).filter(Alert.resolved_at.is_(None)).all()
        return {
            "alerts": [
                {
                    "id": alert.id,
                    "type": alert.type,
                    "message": alert.message,
                    "created_at": alert.created_at.strftime("%Y-%m-%d %H:%M:%S")
                }
                for alert in alerts
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run("app:app", host=host, port=port, reload=True) 