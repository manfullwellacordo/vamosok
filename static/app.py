from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from io import BytesIO
from pathlib import Path
import uvicorn
from datetime import datetime, timedelta
import os
import sys
import psutil
import subprocess
from dotenv import load_dotenv
from analisar_dados_v5 import AnalisadorInteligente, RelatorioDatabase

# Carregar variáveis de ambiente
load_dotenv()

# Criar diretório para templates e arquivos estáticos se não existirem
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

class ServerHealthCheck:
    def __init__(self):
        self.db_path = "F:/relatoriotest/relatorio_dashboard.db"
        self.port = 8000
        self.max_memory_percent = 90  # Limite de uso de memória
        self.max_cpu_percent = 80     # Limite de uso de CPU

    def verificar_porta(self):
        """Verifica se a porta está disponível"""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('localhost', self.port))
            disponivel = True
        except:
            disponivel = False
        finally:
            sock.close()
        return disponivel

    def verificar_banco_dados(self):
        """Verifica a conexão com o banco de dados e sua integridade"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verificar tabelas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tabelas = {row[0] for row in cursor.fetchall()}
            tabelas_necessarias = {'grupos', 'colaboradores', 'relatorio_geral', 'metricas_produtividade'}
            
            # Verificar dados
            dados_ok = True
            for tabela in tabelas_necessarias:
                if tabela not in tabelas:
                    dados_ok = False
                    break
                cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
                if cursor.fetchone()[0] == 0:
                    dados_ok = False
                    break
            
            conn.close()
            return dados_ok
            
        except sqlite3.Error:
            return False

    def verificar_recursos(self):
        """Verifica uso de recursos do sistema"""
        memoria = psutil.virtual_memory().percent
        cpu = psutil.cpu_percent(interval=1)
        return {
            'memoria_ok': memoria < self.max_memory_percent,
            'cpu_ok': cpu < self.max_cpu_percent,
            'memoria_uso': memoria,
            'cpu_uso': cpu
        }

    def corrigir_problemas(self):
        """Tenta corrigir problemas identificados"""
        resultados = {
            'servidor': False,
            'banco_dados': False,
            'recursos': False
        }
        
        # Verificar e corrigir porta
        if not self.verificar_porta():
            try:
                # Tentar matar processo usando a porta
                for proc in psutil.process_iter(['pid', 'name', 'connections']):
                    try:
                        for conn in proc.connections():
                            if conn.laddr.port == self.port:
                                psutil.Process(proc.pid).terminate()
                                break
                    except:
                        continue
                resultados['servidor'] = self.verificar_porta()
            except:
                resultados['servidor'] = False
        else:
            resultados['servidor'] = True
        
        # Verificar e corrigir banco de dados
        if not self.verificar_banco_dados():
            try:
                # Tentar recriar tabelas
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Criar tabelas necessárias
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS grupos (
                    id INTEGER PRIMARY KEY,
                    nome TEXT UNIQUE NOT NULL
                )
                ''')
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS colaboradores (
                    id INTEGER PRIMARY KEY,
                    nome TEXT NOT NULL,
                    grupo_id INTEGER NOT NULL,
                    FOREIGN KEY (grupo_id) REFERENCES grupos (id),
                    UNIQUE (nome, grupo_id)
                )
                ''')
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS relatorio_geral (
                    id INTEGER PRIMARY KEY,
                    colaborador_id INTEGER NOT NULL,
                    data_relatorio DATE NOT NULL,
                    verificado INTEGER DEFAULT 0,
                    analise INTEGER DEFAULT 0,
                    pendente INTEGER DEFAULT 0,
                    prioridade INTEGER DEFAULT 0,
                    prioridade_total INTEGER DEFAULT 0,
                    aprovado INTEGER DEFAULT 0,
                    apreendido INTEGER DEFAULT 0,
                    cancelado INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 0,
                    FOREIGN KEY (colaborador_id) REFERENCES colaboradores (id),
                    UNIQUE (colaborador_id, data_relatorio)
                )
                ''')
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS metricas_produtividade (
                    id INTEGER PRIMARY KEY,
                    colaborador_id INTEGER NOT NULL,
                    data_relatorio DATE NOT NULL,
                    prod_diaria REAL DEFAULT 0,
                    prod_horaria REAL DEFAULT 0,
                    eficiencia REAL DEFAULT 0,
                    FOREIGN KEY (colaborador_id) REFERENCES colaboradores (id),
                    UNIQUE (colaborador_id, data_relatorio)
                )
                ''')
                
                conn.commit()
                conn.close()
                
                # Executar analisador para recarregar dados
                analisador = AnalisadorInteligente()
                analisador.executar_analise_completa()
                analisador.exportar_para_sqlite()
                
                resultados['banco_dados'] = self.verificar_banco_dados()
            except:
                resultados['banco_dados'] = False
        else:
            resultados['banco_dados'] = True
        
        # Verificar e corrigir recursos
        recursos = self.verificar_recursos()
        if not recursos['memoria_ok'] or not recursos['cpu_ok']:
            try:
                # Tentar liberar recursos
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        if proc.cpu_percent() > 50 or proc.memory_percent() > 50:
                            if proc.name() not in ['python.exe', 'pythonw.exe']:
                                proc.terminate()
                    except:
                        continue
                
                recursos = self.verificar_recursos()
                resultados['recursos'] = recursos['memoria_ok'] and recursos['cpu_ok']
            except:
                resultados['recursos'] = False
        else:
            resultados['recursos'] = True
        
        return resultados

app = FastAPI(title="Dashboard de Análise de Contratos")

# Configurar diretórios
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Criar diretórios se não existirem
TEMPLATES_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# Configurar arquivos estáticos e templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Configurar banco de dados
DB_PATH = os.getenv("DB_PATH", "relatorio_dashboard.db")

# Instanciar verificador de saúde do servidor
health_checker = ServerHealthCheck()

# Função para conectar ao banco de dados
def get_db():
    """Função helper para obter conexão com o banco de dados"""
    try:
        conn = sqlite3.connect(DB_PATH)
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao conectar ao banco de dados: {str(e)}")

# Função para gerar gráficos
def gerar_grafico_pizza(df_status):
    plt.figure(figsize=(10, 6))
    labels = ['Verificado', 'Análise', 'Pendente', 'Prioridade', 
              'Prioridade Total', 'Aprovado', 'Apreendido', 'Cancelado']
    valores = [df_status[0][col] for col in ['verificado', 'analise', 'pendente', 'prioridade', 
                                           'prioridade_total', 'aprovado', 'apreendido', 'cancelado']]
    
    plt.pie(valores, labels=labels, autopct='%1.1f%%', startangle=90)
    plt.title('Distribuição de Status')
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    img_str = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close()
    
    return img_str

def gerar_grafico_barras(df_metricas):
    plt.figure(figsize=(12, 8))
    df_top10 = df_metricas.nlargest(10, 'eficiencia')
    sns.barplot(x='colaborador', y='eficiencia', hue='grupo', data=df_top10)
    plt.title('Top 10 Colaboradores por Eficiência')
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    img_str = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close()
    
    return img_str

# Rota principal - Dashboard
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Rota principal que renderiza o dashboard"""
    try:
        conn = get_db()
        
        # Buscar dados do relatório geral
        df_relatorio = pd.read_sql_query("""
            SELECT 
                c.nome as colaborador,
                g.nome as grupo,
                r.*,
                m.prod_diaria,
                m.prod_horaria,
                m.eficiencia
            FROM relatorio_geral r
            JOIN colaboradores c ON r.colaborador_id = c.id
            JOIN grupos g ON c.grupo_id = g.id
            LEFT JOIN metricas_produtividade m ON r.colaborador_id = m.colaborador_id
            ORDER BY r.data_relatorio DESC
        """, conn)
        
        # Calcular totais
        totais = {
            'verificado': df_relatorio['verificado'].sum(),
            'analise': df_relatorio['analise'].sum(),
            'pendente': df_relatorio['pendente'].sum(),
            'prioridade': df_relatorio['prioridade'].sum(),
            'prioridade_total': df_relatorio['prioridade_total'].sum(),
            'aprovado': df_relatorio['aprovado'].sum(),
            'apreendido': df_relatorio['apreendido'].sum(),
            'cancelado': df_relatorio['cancelado'].sum()
        }
        
        # Preparar dados para o template
        context = {
            "request": request,
            "df_relatorio": df_relatorio.to_dict('records'),
            "totais": totais,
            "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        
        return templates.TemplateResponse("dashboard.html", context)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar dashboard: {str(e)}")

# Rota para exportar dados
@app.get("/exportar/{tipo}/{formato}")
async def exportar_dados(tipo: str, formato: str, conn: sqlite3.Connection = Depends(get_db)):
    from fastapi.responses import FileResponse
    
    try:
        cursor = conn.cursor()
        
        if tipo == "diario":
            query = """
            SELECT c.nome as colaborador, g.nome as grupo, rd.*
            FROM relatorio_diario rd
            JOIN colaboradores c ON rd.colaborador_id = c.id
            JOIN grupos g ON c.grupo_id = g.id
            """
            nome_arquivo = "relatorio_diario"
        
        elif tipo == "geral":
            query = """
            SELECT c.nome as colaborador, g.nome as grupo, rg.*
            FROM relatorio_geral rg
            JOIN colaboradores c ON rg.colaborador_id = c.id
            JOIN grupos g ON c.grupo_id = g.id
            """
            nome_arquivo = "relatorio_geral"
        
        elif tipo == "metricas":
            query = """
            SELECT c.nome as colaborador, g.nome as grupo, mp.*
            FROM metricas_produtividade mp
            JOIN colaboradores c ON mp.colaborador_id = c.id
            JOIN grupos g ON c.grupo_id = g.id
            """
            nome_arquivo = "metricas_produtividade"
        
        else:
            raise HTTPException(status_code=400, detail="Tipo de relatório inválido")
        
        # Executar consulta
        cursor.execute(query)
        dados = cursor.fetchall()
        df = pd.DataFrame(dados)
        
        # Caminho para salvar o arquivo
        data_atual = datetime.now().strftime("%Y%m%d")
        caminho_arquivo = f"static/{nome_arquivo}_{data_atual}"
        
        # Exportar conforme formato solicitado
        if formato == "excel":
            caminho_completo = f"{caminho_arquivo}.xlsx"
            df.to_excel(caminho_completo, index=False)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        
        elif formato == "csv":
            caminho_completo = f"{caminho_arquivo}.csv"
            df.to_csv(caminho_completo, index=False)
            media_type = "text/csv"
        
        else:
            raise HTTPException(status_code=400, detail="Formato inválido")
        
        return FileResponse(
            path=caminho_completo,
            filename=os.path.basename(caminho_completo),
            media_type=media_type
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao exportar dados: {str(e)}")

# Criar template HTML
def criar_template_html():
    """Cria o template HTML para o dashboard"""
    template_html = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard de Análise de Contratos</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f8f9fa;
        }
        .card {
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            transition: transform 0.3s;
        }
        .card:hover {
            transform: translateY(-5px);
        }
        .nav-tabs .nav-link {
            color: #495057;
        }
        .nav-tabs .nav-link.active {
            font-weight: bold;
            color: #0d6efd;
        }
        .header {
            background: linear-gradient(120deg, #2c3e50, #4ca1af);
            color: white;
            padding: 20px 0;
            margin-bottom: 30px;
        }
        .status-box {
            text-align: center;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            color: white;
            font-weight: bold;
        }
        .bg-verificado { background-color: #3498db; }
        .bg-analise { background-color: #f39c12; }
        .bg-pendente { background-color: #e74c3c; }
        .bg-prioridade { background-color: #9b59b6; }
        .bg-aprovado { background-color: #2ecc71; }
        .bg-apreendido { background-color: #c0392b; }
        .bg-cancelado { background-color: #7f8c8d; }
        .table-responsive {
            max-height: 400px;
            overflow-y: auto;
        }
        .table th {
            position: sticky;
            top: 0;
            background-color: #f8f9fa;
            z-index: 10;
        }
    </style>
</head>
<body>
    <div class="header text-center">
        <h1>Análise de Contratos</h1>
        <p class="lead">Dashboard Interativo</p>
    </div>

    <div class="container">
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <h3>Dashboard</h3>
                    </div>
                    <div class="card-body">
                        <ul class="nav nav-tabs" id="myTab" role="tablist">
                            <li class="nav-item" role="presentation">
                                <button class="nav-link active" id="overview-tab" data-bs-toggle="tab" data-bs-target="#overview" type="button" role="tab">Visão Geral</button>
                            </li>
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="collaborators-tab" data-bs-toggle="tab" data-bs-target="#collaborators" type="button" role="tab">Colaboradores</button>
                            </li>
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="reports-tab" data-bs-toggle="tab" data-bs-target="#reports" type="button" role="tab">Relatórios</button>
                            </li>
                        </ul>
                        
                        <div class="tab-content mt-3" id="myTabContent">
                            <!-- Visão Geral -->
                            <div class="tab-pane fade show active" id="overview" role="tabpanel">
                                <div class="row">
                                    <div class="col-md-4">
                                        <div class="card">
                                            <div class="card-header bg-info text-white">
                                                <h4>Grupos</h4>
                                            </div>
                                            <div class="card-body">
                                                <div class="table-responsive">
                                                    <table class="table table-hover">
                                                        <thead>
                                                            <tr>
                                                                <th>Grupo</th>
                                                                <th>Colaboradores</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {% for grupo in grupos %}
                                                            <tr>
                                                                <td>{{ grupo.nome }}</td>
                                                                <td>{{ grupo.total_colaboradores }}</td>
                                                            </tr>
                                                            {% endfor %}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div class="col-md-8">
                                        <div class="card">
                                            <div class="card-header bg-info text-white">
                                                <h4>Distribuição de Status</h4>
                                            </div>
                                            <div class="card-body text-center">
                                                <img src="data:image/png;base64,{{ grafico_pizza }}" class="img-fluid">
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="row mt-4">
                                    <div class="col-md-12">
                                        <div class="card">
                                            <div class="card-header bg-info text-white">
                                                <h4>Status</h4>
                                            </div>
                                            <div class="card-body">
                                                <div class="row">
                                                    <div class="col-md-3">
                                                        <div class="status-box bg-verificado">
                                                            VERIFICADO: {{ status.verificado }}
                                                        </div>
                                                    </div>
                                                    <div class="col-md-3">
                                                        <div class="status-box bg-analise">
                                                            ANÁLISE: {{ status.analise }}
                                                        </div>
                                                    </div>
                                                    <div class="col-md-3">
                                                        <div class="status-box bg-pendente">
                                                            PENDENTE: {{ status.pendente }}
                                                        </div>
                                                    </div>
                                                    <div class="col-md-3">
                                                        <div class="status-box bg-prioridade">
                                                            PRIORIDADE: {{ status.prioridade }}
                                                        </div>
                                                    </div>
                                                </div>
                                                <div class="row mt-3">
                                                    <div class="col-md-3">
                                                        <div class="status-box bg-aprovado">
                                                            APROVADO: {{ status.aprovado }}
                                                        </div>
                                                    </div>
                                                    <div class="col-md-3">
                                                        <div class="status-box bg-apreendido">
                                                            APREENDIDO: {{ status.apreendido }}
                                                        </div>
                                                    </div>
                                                    <div class="col-md-3">
                                                        <div class="status-box bg-cancelado">
                                                            CANCELADO: {{ status.cancelado }}
                                                        </div>
                                                    </div>
                                                    <div class="col-md-3">
                                                        <div class="status-box" style="background-color: #1abc9c;">
                                                            PRIORIDADE TOTAL: {{ status.prioridade_total }}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Colaboradores -->
                            <div class="tab-pane fade" id="collaborators" role="tabpanel">
                                <div class="row">
                                    <div class="col-md-12">
                                        <div class="card">
                                            <div class="card-header bg-success text-white">
                                                <h4>Top Colaboradores</h4>
                                            </div>
                                            <div class="card-body text-center">
                                                <img src="data:image/png;base64,{{ grafico_barras }}" class="img-fluid">
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="row mt-4">
                                    <div class="col-md-12">
                                        <div class="card">
                                            <div class="card-header bg-success text-white">
                                                <h4>Métricas por Colaborador</h4>
                                            </div>
                                            <div class="card-body">
                                                <div class="table-responsive">
                                                    <table class="table table-striped table-hover">
                                                        <thead>
                                                            <tr>
                                                                <th>Colaborador</th>
                                                                <th>Grupo</th>
                                                                <th>Total</th>
                                                                <th>Prod. Diária</th>
                                                                <th>Prod. Horária</th>
                                                                <th>Eficiência (%)</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {% for m in metricas %}
                                                            <tr>
                                                                <td>{{ m.colaborador }}</td>
                                                                <td>{{ m.grupo }}</td>
                                                                <td>{{ m.total }}</td>
                                                                <td>{{ "%.1f"|format(m.prod_diaria) }}</td>
                                                                <td>{{ "%.2f"|format(m.prod_horaria) }}</td>
                                                                <td>{{ "%.1f"|format(m.eficiencia) }}</td>
                                                            </tr>
                                                            {% endfor %}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Relatórios -->
                            <div class="tab-pane fade" id="reports" role="tabpanel">
                                <div class="row">
                                    <div class="col-md-12">
                                        <div class="card">
                                            <div class="card-header bg-warning text-dark">
                                                <h4>Exportar Relatórios</h4>
                                            </div>
                                            <div class="card-body">
                                                <div class="row">
                                                    <div class="col-md-6">
                                                        <div class="mb-3">
                                                            <label for="reportType" class="form-label">Tipo de Relatório</label>
                                                            <select class="form-select" id="reportType">
                                                                <option value="diario">Relatório Diário</option>
                                                                <option value="geral">Relatório Geral</option>
                                                                <option value="metricas">Métricas de Produtividade</option>
                                                            </select>
                                                        </div>
                                                    </div>
                                                    <div class="col-md-6">
                                                        <div class="mb-3">
                                                            <label for="exportFormat" class="form-label">Formato</label>
                                                            <select class="form-select" id="exportFormat">
                                                                <option value="excel">Excel</option>
                                                                <option value="csv">CSV</option>
                                                            </select>
                                                        </div>
                                                    </div>
                                                </div>
                                                <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                                                    <button type="button" class="btn btn-primary" id="exportBtn">
                                                        <i class="bi bi-download me-1"></i> Exportar
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Exportar relatórios
            document.getElementById('exportBtn').addEventListener('click', function() {
                const reportType = document.getElementById('reportType').value;
                const exportFormat = document.getElementById('exportFormat').value;
                
                window.location.href = `/exportar/${reportType}/${exportFormat}`;
            });
        });
    </script>
</body>
</html>
    """
    
    # Criar diretório de templates se não existir
    os.makedirs("templates", exist_ok=True)
    
    # Salvar o template
    with open("templates/dashboard.html", "w", encoding="utf-8") as f:
        f.write(template_html)
    
    print("Template HTML criado com sucesso!")

# Adicione esta rota para verificar se o servidor está funcionando
@app.get("/status")
async def status():
    return {"status": "online", "message": "Servidor funcionando corretamente"}

@app.get("/health")
async def health_check():
    """Endpoint para verificar a saúde do servidor e corrigir problemas"""
    status = {
        'servidor': health_checker.verificar_porta(),
        'banco_dados': health_checker.verificar_banco_dados(),
        'recursos': health_checker.verificar_recursos()
    }
    
    # Se houver problemas, tentar corrigir
    if not all([status['servidor'], status['banco_dados'], status['recursos']['memoria_ok'], status['recursos']['cpu_ok']]):
        correcoes = health_checker.corrigir_problemas()
        status['correcoes'] = correcoes
        
        if all(correcoes.values()):
            status['message'] = "Problemas corrigidos com sucesso"
        else:
            status['message'] = "Alguns problemas não puderam ser corrigidos"
            
            # Identificar problemas específicos
            problemas = []
            if not correcoes['servidor']:
                problemas.append("Servidor não pôde ser reiniciado")
            if not correcoes['banco_dados']:
                problemas.append("Banco de dados não pôde ser recuperado")
            if not correcoes['recursos']:
                problemas.append("Recursos do sistema continuam sobrecarregados")
            
            status['problemas'] = problemas
    else:
        status['message'] = "Todos os sistemas funcionando normalmente"
    
    return status

@app.post("/atualizar")
async def atualizar_dados():
    """Rota para atualizar os dados do dashboard"""
    try:
        analisador = AnalisadorInteligente()
        analisador.executar_analise_completa()
        analisador.exportar_para_sqlite()
        return {"message": "Dados atualizados com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar dados: {str(e)}")

# Iniciar o servidor se executado diretamente
if __name__ == "__main__":
    criar_template_html()
    print("Iniciando servidor FastAPI na porta 8000...")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True) 