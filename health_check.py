from sqlalchemy import create_engine, func, text, inspect, case
from sqlalchemy.orm import sessionmaker
from models import Contract, DailyMetrics, Alert, Base
import os
from dotenv import load_dotenv
from datetime import datetime
import sys
import time
import psutil

# Load environment variables
load_dotenv()

class HealthCheck:
    def __init__(self):
        self.DB_PATH = os.getenv("DB_PATH", "relatorio_dashboard.db")
        self.engine = create_engine(f"sqlite:///{self.DB_PATH}")
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.errors = []
        self.warnings = []
        self.performance_metrics = {}

    def check_system_resources(self):
        """Verifica recursos do sistema"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            self.performance_metrics.update({
                'cpu_usage': cpu_percent,
                'memory_usage': memory.percent,
                'disk_usage': disk.percent
            })

            warnings = []
            if cpu_percent > 80:
                warnings.append(f"CPU usage is high: {cpu_percent}%")
            if memory.percent > 80:
                warnings.append(f"Memory usage is high: {memory.percent}%")
            if disk.percent > 80:
                warnings.append(f"Disk usage is high: {disk.percent}%")

            if warnings:
                self.warnings.extend(warnings)
                print("⚠️ System resources: WARNING")
                for warning in warnings:
                    print(f"  - {warning}")
            else:
                print("✅ System resources: OK")

            return True
        except Exception as e:
            self.errors.append(f"Error checking system resources: {str(e)}")
            print(f"❌ System resources check failed: {str(e)}")
            return False

    def check_database_connection(self):
        """Verifica a conexão com o banco de dados"""
        start_time = time.time()
        try:
            # Usar text() para declarar explicitamente a consulta SQL
            self.session.execute(text("SELECT 1"))
            response_time = time.time() - start_time
            
            self.performance_metrics['db_response_time'] = response_time
            
            if response_time > 1.0:
                self.warnings.append(f"Database response time is slow: {response_time:.2f}s")
                print(f"⚠️ Database connection: SLOW ({response_time:.2f}s)")
            else:
                print(f"✅ Database connection: OK ({response_time:.2f}s)")
            return True
        except Exception as e:
            self.errors.append(f"Database connection error: {str(e)}")
            print(f"❌ Database connection: FAILED - {str(e)}")
            return False

    def check_tables_exist(self):
        """Verifica se todas as tabelas necessárias existem e sua integridade"""
        try:
            # Criar as tabelas se não existirem
            Base.metadata.create_all(self.engine)
            
            # Verificar se as tabelas foram criadas
            inspector = inspect(self.engine)
            existing_tables = set(inspector.get_table_names())
            required_tables = {Contract.__tablename__, DailyMetrics.__tablename__, Alert.__tablename__}
            
            # Verificar índices e constraints
            for table_name in required_tables:
                if table_name in existing_tables:
                    indexes = inspector.get_indexes(table_name)
                    if not indexes:
                        self.warnings.append(f"Table {table_name} has no indexes")
                
            missing_tables = required_tables - existing_tables
            if missing_tables:
                self.errors.append(f"Missing tables: {missing_tables}")
                print(f"❌ Tables missing: {missing_tables}")
                return False
            
            print("✅ Table structure: OK")
            return True
        except Exception as e:
            self.errors.append(f"Error checking/creating tables: {str(e)}")
            print(f"❌ Table check failed: {str(e)}")
            return False

    def check_data_integrity(self):
        """Verifica a integridade dos dados"""
        try:
            start_time = time.time()
            
            # Verificar total de contratos
            total_contracts = self.session.query(Contract).count()
            if total_contracts == 0:
                print("⚠️ Contract data: EMPTY")
                self.warnings.append("No contracts found in database")
                return True

            # Verificar duplicatas
            duplicate_contracts = self.session.query(
                Contract.contract_number,
                func.count(Contract.contract_number)
            ).group_by(Contract.contract_number).having(func.count(Contract.contract_number) > 1).all()

            if duplicate_contracts:
                self.warnings.append(f"Found {len(duplicate_contracts)} duplicate contract numbers")
                print(f"⚠️ Found duplicate contracts: {len(duplicate_contracts)}")

            # Verificar grupos
            groups = self.session.query(
                case(
                    (Contract.contract_number.like("JULIO-%"), "JULIO"),
                    else_="LEANDRO"
                ).label('grupo'),
                func.count('*').label('count')
            ).group_by('grupo').all()

            if len(groups) != 2:
                self.warnings.append("Data not distributed between both groups (JULIO and LEANDRO)")
                print("⚠️ Group distribution: INCONSISTENT")
            
            # Verificar status inválidos
            invalid_status = self.session.query(Contract).filter(
                ~Contract.status.in_([
                    'verified', 'analysis', 'approved', 'pending',
                    'paid', 'seized', 'priority', 'high_priority',
                    'cancelled', 'other'
                ])
            ).count()

            if invalid_status > 0:
                self.warnings.append(f"Found {invalid_status} contracts with invalid status")
                print(f"⚠️ Invalid status found: {invalid_status} contracts")

            processing_time = time.time() - start_time
            self.performance_metrics['data_check_time'] = processing_time

            print("\nData Distribution:")
            print("-" * 40)
            print(f"Total contracts: {total_contracts}")
            print(f"Processing time: {processing_time:.2f}s")
            
            print("\nBy group:")
            for group, count in groups:
                print(f"- {group}: {count} contracts")

            print("\n✅ Data integrity: OK")
            return True

        except Exception as e:
            self.errors.append(f"Data integrity check error: {str(e)}")
            print(f"❌ Data integrity: FAILED - {str(e)}")
            return False

    def check_metrics_consistency(self):
        """Verifica a consistência das métricas"""
        try:
            start_time = time.time()

            # Verificar métricas ausentes
            contracts_without_metrics = self.session.query(Contract).filter(
                ~Contract.id.in_(
                    self.session.query(DailyMetrics.contract_id)
                )
            ).count()

            if contracts_without_metrics > 0:
                self.warnings.append(f"{contracts_without_metrics} contracts without daily metrics")
                print(f"⚠️ Daily metrics: {contracts_without_metrics} contracts missing metrics")
            
            # Verificar valores das métricas
            invalid_metrics = self.session.query(DailyMetrics).filter(
                (DailyMetrics.productivity < 0) |
                (DailyMetrics.productivity > 1) |
                (DailyMetrics.efficiency < 0) |
                (DailyMetrics.efficiency > 1) |
                (DailyMetrics.resolution_rate < 0) |
                (DailyMetrics.resolution_rate > 1)
            ).count()

            if invalid_metrics > 0:
                self.warnings.append(f"{invalid_metrics} metrics with invalid values")
                print(f"⚠️ Metric values: {invalid_metrics} invalid metrics")

            # Verificar consistência temporal
            latest_metric = self.session.query(
                func.max(DailyMetrics.date)
            ).scalar()

            if latest_metric:
                days_old = (datetime.now().date() - latest_metric).days
                if days_old > 1:
                    self.warnings.append(f"Metrics are {days_old} days old")
                    print(f"⚠️ Metric freshness: {days_old} days old")

            processing_time = time.time() - start_time
            self.performance_metrics['metrics_check_time'] = processing_time

            print(f"\n✅ Metrics consistency: OK (processed in {processing_time:.2f}s)")
            return True

        except Exception as e:
            self.errors.append(f"Metrics consistency check error: {str(e)}")
            print(f"❌ Metrics consistency: FAILED - {str(e)}")
            return False

    def run_all_checks(self):
        """Executa todas as verificações"""
        print("\n=== Starting System Health Check ===\n")
        start_time = time.time()
        
        checks = [
            self.check_system_resources,
            self.check_database_connection,
            self.check_tables_exist,
            self.check_data_integrity,
            self.check_metrics_consistency
        ]

        all_passed = all(check() for check in checks)
        total_time = time.time() - start_time

        print("\n=== Health Check Summary ===")
        if self.errors:
            print("\nCritical Errors:")
            for error in self.errors:
                print(f"❌ {error}")

        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"⚠️ {warning}")

        print("\nPerformance Metrics:")
        for metric, value in self.performance_metrics.items():
            print(f"- {metric}: {value:.2f}")

        print(f"\nTotal check time: {total_time:.2f}s")

        if all_passed and not self.warnings:
            print("\n✅ System ready to start!")
        elif all_passed:
            print("\n🟡 System can start with warnings.")
        else:
            print("\n❌ System cannot start due to critical errors.")

        return all_passed

if __name__ == "__main__":
    checker = HealthCheck()
    if not checker.run_all_checks():
        sys.exit(1)  # Exit with error if checks fail 