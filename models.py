from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    contract_number = Column(String, unique=True, index=True)
    collaborator = Column(String, index=True)
    status = Column(String, index=True)
    resolution_time = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    daily_metrics = relationship("DailyMetric", back_populates="contract")
    alerts = relationship("Alert", back_populates="contract")

class DailyMetric(Base):
    __tablename__ = "daily_metrics"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), index=True)
    date = Column(DateTime, index=True)
    productivity = Column(Float)
    efficiency = Column(Float)
    resolution_rate = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    contract = relationship("Contract", back_populates="daily_metrics")

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), index=True)
    type = Column(String)
    message = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)

    contract = relationship("Contract", back_populates="alerts")

def init_db(db_url):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine 