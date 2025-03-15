from sqlalchemy import create_engine, func, text, inspect, case
from sqlalchemy.orm import sessionmaker
from models import Contract, DailyMetric, Alert, Base
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

    def format_error(self, message, error=None):
        """Formata mensagens de erro de forma consistente"""
        if error:
            return "{}: {}".format(message, str(error))
        return message

    def check_system_resources(self):
        """Verifica recursos do sistema"""
        try:
            # Coletar métricas do sistema
            try:
                cpu_percent = float(psutil.cpu_percent(interval=1))
            except Exception:
                cpu_percent = 0.0

            try:
                memory = psutil.virtual_memory()
                memory_percent = float(memory.percent)
            except Exception:
                memory_percent = 0.0

            try:
                disk = psutil.disk_usage('/')
                disk_percent = float(disk.percent)
            except Exception:
                disk_percent = 0.0

            # Atualizar métricas
            self.performance_metrics.update({
                'cpu_usage': cpu_percent,
                'memory_usage': memory_percent,
                'disk_usage': disk_percent
            })

            # Verificar limites
            warnings = []
            try:
                if cpu_percent > 80:
                    warnings.append("CPU usage is high: %.1f%%" % cpu_percent)
                if memory_percent > 80:
                    warnings.append("Memory usage is high: %.1f%%" % memory_percent)
                if disk_percent > 80:
                    warnings.append("Disk usage is high: %.1f%%" % disk_percent)
            except Exception as e:
                warnings.append("Error formatting resource warnings: " + str(e))

            # Exibir resultados
            if warnings:
                self.warnings.extend(warnings)
                print("⚠️ System resources: WARNING")
                for warning in warnings:
                    print("  - " + str(warning))
            else:
                print("✅ System resources: OK")

            return True

        except Exception as e:
            error_msg = "Error checking system resources: " + str(e)
            self.errors.append(error_msg)
            print("❌ System resources check failed: " + str(error_msg))
            return False

    def check_database_connection(self):
        """Verifica a conexão com o banco de dados"""
        start_time = time.time()
        try:
            self.session.execute(text("SELECT 1"))
            response_time = time.time() - start_time
            
            self.performance_metrics['db_response_time'] = response_time
            
            if response_time > 1.0:
                warning_msg = "Database response time is slow: {:.2f}s".format(response_time)
                self.warnings.append(warning_msg)
                print("⚠️ Database connection: SLOW ({:.2f}s)".format(response_time))
            else:
                print("✅ Database connection: OK ({:.2f}s)".format(response_time))
            return True
        except Exception as e:
            error_msg = self.format_error("Database connection error", e)
            self.errors.append(error_msg)
            print("❌ Database connection: FAILED - {}".format(error_msg))
            return False

    def check_tables_exist(self):
        """Verifica se todas as tabelas necessárias existem e sua integridade"""
        try:
            # Criar as tabelas se não existirem
            Base.metadata.create_all(self.engine)
            
            # Verificar se as tabelas foram criadas
            inspector = inspect(self.engine)
            existing_tables = set(inspector.get_table_names())
            required_tables = {Contract.__tablename__, DailyMetric.__tablename__, Alert.__tablename__}
            
            # Verificar índices e constraints
            for table_name in required_tables:
                if table_name in existing_tables:
                    indexes = inspector.get_indexes(table_name)
                    if not indexes:
                        self.warnings.append("Table {} has no indexes".format(table_name))
                
            missing_tables = required_tables - existing_tables
            if missing_tables:
                error_msg = "Missing tables: {}".format(missing_tables)
                self.errors.append(error_msg)
                print("❌ Tables missing: {}".format(missing_tables))
                return False
            
            print("✅ Table structure: OK")
            return True
        except Exception as e:
            error_msg = self.format_error("Error checking/creating tables", e)
            self.errors.append(error_msg)
            print("❌ Table check failed: {}".format(error_msg))
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
                warning_msg = "Found {} duplicate contract numbers".format(len(duplicate_contracts))
                self.warnings.append(warning_msg)
                print("⚠️ Found duplicate contracts: {}".format(len(duplicate_contracts)))

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
                warning_msg = "Found {} contracts with invalid status".format(invalid_status)
                self.warnings.append(warning_msg)
                print("⚠️ Invalid status found: {} contracts".format(invalid_status))

            processing_time = time.time() - start_time
            self.performance_metrics['data_check_time'] = processing_time

            print("\nData Distribution:")
            print("-" * 40)
            print("Total contracts: {}".format(total_contracts))
            print("Processing time: {:.2f}s".format(processing_time))
            
            print("\nBy group:")
            for group, count in groups:
                print("- {}: {} contracts".format(group, count))

            print("\n✅ Data integrity: OK")
            return True

        except Exception as e:
            error_msg = self.format_error("Data integrity check error", e)
            self.errors.append(error_msg)
            print("❌ Data integrity: FAILED - {}".format(error_msg))
            return False

    def check_metrics_consistency(self):
        """Verifica a consistência das métricas"""
        try:
            start_time = time.time()

            # Verificar métricas ausentes
            contracts_without_metrics = self.session.query(Contract).filter(
                ~Contract.id.in_(
                    self.session.query(DailyMetric.contract_id)
                )
            ).count()

            if contracts_without_metrics > 0:
                warning_msg = "{} contracts without daily metrics".format(contracts_without_metrics)
                self.warnings.append(warning_msg)
                print("⚠️ Daily metrics: {} contracts missing metrics".format(contracts_without_metrics))

            # Verificar valores das métricas
            invalid_metrics = self.session.query(DailyMetric).filter(
                (DailyMetric.productivity < 0) |
                (DailyMetric.productivity > 1) |
                (DailyMetric.efficiency < 0) |
                (DailyMetric.efficiency > 1)
            ).count()

            if invalid_metrics > 0:
                warning_msg = "Found {} metrics with invalid values".format(invalid_metrics)
                self.warnings.append(warning_msg)
                print("⚠️ Invalid metrics found: {}".format(invalid_metrics))

            processing_time = time.time() - start_time
            self.performance_metrics['metrics_check_time'] = processing_time

            print("✅ Metrics consistency: OK")
            return True

        except Exception as e:
            error_msg = self.format_error("Metrics consistency check error", e)
            self.errors.append(error_msg)
            print("❌ Metrics consistency: FAILED - {}".format(error_msg))
            return False

    def run_all_checks(self):
        """Executa todas as verificações de saúde do sistema"""
        print("\n=== Running System Health Checks ===\n")
        
        checks = [
            self.check_system_resources,
            self.check_database_connection,
            self.check_tables_exist,
            self.check_data_integrity,
            self.check_metrics_consistency
        ]
        
        results = []
        for check in checks:
            try:
                results.append(check())
            except Exception as e:
                error_msg = self.format_error("Unexpected error in {}".format(check.__name__), e)
                self.errors.append(error_msg)
                results.append(False)
        
        print("\n=== Health Check Summary ===")
        print("Errors: {}".format(len(self.errors)))
        print("Warnings: {}".format(len(self.warnings)))
        
        return all(results) and not self.errors

if __name__ == "__main__":
    checker = HealthCheck()
    if not checker.run_all_checks():
        sys.exit(1)  # Exit with error if checks fail 