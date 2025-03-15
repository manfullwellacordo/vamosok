import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from models import Contract, DailyMetric, Alert, init_db
import os
from dotenv import load_dotenv
import numpy as np
from sqlalchemy import func

# Load environment variables
load_dotenv()

# Initialize database
DB_PATH = os.getenv("DB_PATH", "relatorio_dashboard.db")
engine = init_db(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def convert_to_days(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (datetime, pd.Timestamp)):
        today = pd.Timestamp.now()
        return (today - pd.Timestamp(value)).days
    return None

def process_excel_file(file_path, grupo):
    print(f"\nProcessando arquivo: {file_path}")
    try:
        # Tentar ler todas as abas do Excel
        xlsx = pd.ExcelFile(file_path)
        print(f"Abas encontradas: {xlsx.sheet_names}")
        
        total_imported = 0
        status_counts = {}
        
        for sheet_name in xlsx.sheet_names:
            print(f"\nLendo aba: {sheet_name}")
            df = pd.read_excel(xlsx, sheet_name=sheet_name)
            print(f"Colunas encontradas:")
            print(df.columns.tolist())
            
            # Verificar se as colunas necessárias existem
            if 'SITUAÇÃO' not in df.columns:
                print(f"Aviso: Coluna 'SITUAÇÃO' não encontrada na aba {sheet_name}")
                continue
                
            if 'RESOLUÇÃO' not in df.columns:
                print(f"Aviso: Coluna 'RESOLUÇÃO' não encontrada na aba {sheet_name}")
                continue
            
            # Mapear status
            status_map = {
                'VERIFICADO': 'verified',
                'ANÁLISE': 'analysis',
                'PENDENTE': 'pending',
                'PRIORIDADE': 'priority',
                'PRIORIDADE TOTAL': 'high_priority',
                'APROVADO': 'approved',
                'QUITADO': 'paid',
                'APREENDIDO': 'seized',
                'CANCELADO': 'cancelled'
            }
            
            # Processar cada linha do Excel
            for idx, row in df.iterrows():
                situacao = str(row['SITUAÇÃO']).strip().upper() if pd.notna(row['SITUAÇÃO']) else ''
                resolucao = convert_to_days(row['RESOLUÇÃO'])
                
                # Contar status para estatísticas
                if situacao:
                    if situacao not in status_counts:
                        status_counts[situacao] = 0
                    status_counts[situacao] += 1
                
                # Criar contrato para todos os status
                try:
                    # Criar contrato
                    contract = Contract(
                        contract_number=f"{grupo}-{sheet_name}-{idx}",
                        collaborator=sheet_name,  # Usar o nome da aba como colaborador
                        status=status_map.get(situacao, 'other'),  # Usar 'other' para status não mapeados
                        resolution_time=resolucao,
                        created_at=datetime.now() - timedelta(days=np.random.randint(0, 30))
                    )
                    db.add(contract)
                    db.flush()
                    
                    # Criar métricas
                    metrics = DailyMetric(
                        contract_id=contract.id,
                        date=datetime.now(),
                        productivity=np.random.uniform(0.6, 1.0),
                        efficiency=np.random.uniform(0.7, 1.0),
                        resolution_rate=np.random.uniform(0.5, 1.0)
                    )
                    db.add(metrics)
                    total_imported += 1
                    
                except Exception as e:
                    print(f"Erro ao processar linha {idx}: {str(e)}")
                    continue
            
            db.commit()
            print(f"Importados {total_imported} registros da aba {sheet_name}")
        
        print(f"\nTotal de registros importados do arquivo {file_path}: {total_imported}")
        print("\nContagem de status:")
        for status, count in status_counts.items():
            print(f"{status}: {count}")
        
    except Exception as e:
        print(f"Erro ao processar arquivo {file_path}: {str(e)}")
        db.rollback()

# Limpar dados existentes
print("Limpando dados existentes...")
db.query(Alert).delete()
db.query(DailyMetric).delete()
db.query(Contract).delete()
db.commit()

# Importar dados dos arquivos Excel
excel_files = [
    ("(JULIO) LISTAS INDIVIDUAIS.xlsx", "JULIO"),
    ("(LEANDRO_ADRIANO) LISTAS INDIVIDUAIS.xlsx", "LEANDRO")
]

for file_name, grupo in excel_files:
    file_path = os.path.join("data", file_name)
    if os.path.exists(file_path):
        process_excel_file(file_path, grupo)
    else:
        print(f"Arquivo não encontrado: {file_path}")

# Verificar dados importados
print("\nVerificando dados importados:")
total_contracts = db.query(Contract).count()
print(f"Total de contratos: {total_contracts}")

print("\nContratos por colaborador:")
collaborator_counts = db.query(Contract.collaborator, func.count(Contract.id)).group_by(Contract.collaborator).all()
for collaborator, count in collaborator_counts:
    print(f"{collaborator}: {count} contratos")

print("\nContratos por status:")
status_counts = db.query(Contract.status, func.count(Contract.id)).group_by(Contract.status).all()
for status, count in status_counts:
    print(f"{status}: {count} contratos")

db.close()
print("\nImportação concluída!") 