# Dashboard de Análise de Contratos

Um sistema de dashboard moderno para análise e monitoramento de contratos em tempo real, construído com FastAPI, WebSockets, Plotly Dash e SQLite.

## Características

- 🚀 Dashboard em tempo real com WebSockets
- 📊 Visualizações interativas com Plotly
- 🔔 Sistema de alertas em tempo real
- 📱 Design responsivo e moderno
- 🔒 Banco de dados SQLite para persistência
- 🐳 Containerização com Docker

## Requisitos

- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)
- Docker (opcional, para containerização)
- Navegador web moderno

## Instalação Local

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/dashboard-contratos.git
cd dashboard-contratos
```

2. Crie e ative um ambiente virtual:
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite o arquivo .env com suas configurações
# DB_PATH=relatorio_dashboard.db
# PORT=8001
# HOST=127.0.0.1
# ENVIRONMENT=development
```

5. Execute o servidor:
```bash
uvicorn app:app --reload --port 8001
```

6. Acesse o dashboard em `http://localhost:8001`

## Execução com Docker

1. Construa e inicie os containers:
```bash
docker-compose up -d
```

2. Acesse o dashboard em `http://localhost:8001`

Para parar os containers:
```bash
docker-compose down
```

## Estrutura do Projeto

```
dashboard-contratos/
├── app.py              # Aplicação FastAPI principal
├── models.py           # Modelos SQLAlchemy
├── websocket_manager.py # Gerenciador de WebSockets
├── templates/          # Templates HTML
│   └── dashboard.html
├── static/            # Arquivos estáticos
│   ├── styles.css
│   └── scripts.js
├── data/             # Diretório para banco de dados
├── tests/            # Testes unitários
├── Dockerfile        # Configuração Docker
├── docker-compose.yml # Configuração Docker Compose
└── requirements.txt  # Dependências Python
```

## API Endpoints

- `GET /` - Dashboard principal
- `GET /api/metrics` - Métricas em tempo real
- `GET /api/alerts` - Alertas ativos
- `WS /ws/metrics` - WebSocket para métricas
- `WS /ws/alerts` - WebSocket para alertas

## Desenvolvimento

### Executando Testes

```bash
pytest -v
```

### Verificando Cobertura de Testes

```bash
pytest --cov=. tests/
```

### Linting e Formatação

```bash
# Verificar estilo de código
flake8 .

# Formatar código
black .
```

## Implantação

### Google Cloud Run

1. Instale o Google Cloud SDK
2. Configure o projeto:
```bash
gcloud init
gcloud config set project seu-projeto
```

3. Construa e envie a imagem:
```bash
gcloud builds submit --tag gcr.io/seu-projeto/dashboard-contratos
```

4. Implante no Cloud Run:
```bash
gcloud run deploy dashboard-contratos \
  --image gcr.io/seu-projeto/dashboard-contratos \
  --platform managed \
  --allow-unauthenticated \
  --region us-central1
```

### Heroku

1. Instale o Heroku CLI
2. Faça login e crie um novo app:
```bash
heroku login
heroku create dashboard-contratos
```

3. Configure as variáveis de ambiente:
```bash
heroku config:set ENVIRONMENT=production
```

4. Implante:
```bash
git push heroku main
```

### Railway

1. Conecte sua conta GitHub ao Railway
2. Crie um novo projeto a partir do repositório
3. Configure as variáveis de ambiente
4. Railway detectará automaticamente o Dockerfile e fará a implantação

## Manutenção

### Backup do Banco de Dados

```bash
# Local
sqlite3 data/relatorio_dashboard.db ".backup 'backup.db'"

# No container Docker
docker-compose exec web sqlite3 /app/data/relatorio_dashboard.db ".backup '/app/data/backup.db'"
```

### Atualização de Dependências

```bash
pip install --upgrade -r requirements.txt
```

## Solução de Problemas

### Erro de Conexão com o Banco de Dados

1. Verifique se o arquivo do banco de dados existe
2. Confirme as permissões do arquivo
3. Verifique a variável de ambiente `DB_PATH`

### Erro ao Carregar Dados

1. Verifique os logs do servidor
2. Confirme se todas as tabelas foram criadas
3. Verifique a conexão WebSocket no console do navegador

### Problemas de Performance

1. Monitore o uso de recursos
2. Verifique o tamanho do banco de dados
3. Considere adicionar índices às tabelas mais consultadas

## Contribuindo

1. Fork o repositório
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## Suporte

Para suporte, envie um email para suporte@exemplo.com ou abra uma issue no GitHub.

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes. 