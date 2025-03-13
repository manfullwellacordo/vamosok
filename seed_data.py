from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from models import Contract, DailyMetrics, Alert, init_db
import random
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize database
DB_PATH = os.getenv("DB_PATH", "relatorio_dashboard.db")
engine = init_db(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Sample data
statuses = ["pending", "analyzing", "completed"]
collaborators = ["João Silva", "Maria Santos", "Pedro Oliveira", "Ana Costa"]

# Create contracts
for i in range(20):
    contract = Contract(
        contract_number=f"CONT-{2024}-{i+1:03d}",
        collaborator=random.choice(collaborators),
        status=random.choice(statuses),
        resolution_time=random.uniform(1, 48) if random.random() > 0.3 else None,
        created_at=datetime.now() - timedelta(days=random.randint(0, 30))
    )
    db.add(contract)

db.commit()

# Create daily metrics
contracts = db.query(Contract).all()
for contract in contracts:
    for i in range(5):
        metrics = DailyMetrics(
            contract_id=contract.id,
            date=datetime.now() - timedelta(days=i),
            productivity=random.uniform(0.6, 1.0),
            efficiency=random.uniform(0.7, 1.0),
            resolution_rate=random.uniform(0.5, 1.0)
        )
        db.add(metrics)

# Create alerts
alert_types = ["warning", "critical", "info"]
alert_messages = [
    "Contrato próximo do prazo limite",
    "Atraso na análise detectado",
    "Nova atualização disponível",
    "Documentação pendente",
    "Revisão necessária"
]

for _ in range(5):
    alert = Alert(
        contract_id=random.choice(contracts).id,
        type=random.choice(alert_types),
        message=random.choice(alert_messages),
        created_at=datetime.now() - timedelta(hours=random.randint(1, 24))
    )
    db.add(alert)

db.commit()
db.close()

print("Dados de exemplo adicionados com sucesso!") 