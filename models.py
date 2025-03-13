from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Contract(Base):
    __tablename__ = 'contracts'
    
    id = Column(Integer, primary_key=True)
    contract_number = Column(String(50), unique=True)
    collaborator = Column(String(100))
    status = Column(String(50))
    resolution_time = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    metrics = relationship("DailyMetrics", back_populates="contract")
    alerts = relationship("Alert", back_populates="contract")

class DailyMetrics(Base):
    __tablename__ = 'daily_metrics'
    
    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey('contracts.id'))
    date = Column(DateTime)
    productivity = Column(Float)
    efficiency = Column(Float)
    resolution_rate = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    contract = relationship("Contract", back_populates="metrics")

class Alert(Base):
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey('contracts.id'))
    type = Column(String(50))  # 'warning', 'critical', 'info'
    message = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    contract = relationship("Contract", back_populates="alerts")

def init_db(db_url):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine 