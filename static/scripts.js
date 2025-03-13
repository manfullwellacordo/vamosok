// WebSocket Connections
let metricsWs = null;
let alertsWs = null;

// Chart Objects
let statusChart = null;
let resolutionChart = null;

// Cache for collaborators by group
let collaboratorsByGroup = {
    'JULIO': [],
    'LEANDRO': []
};

// Loading state
let isLoading = false;

// Frontend health check
function checkFrontendHealth() {
    const healthChecks = {
        websockets: false,
        charts: false,
        filters: false,
        data: false
    };

    // Verificar WebSockets
    if (metricsWs && metricsWs.readyState === WebSocket.OPEN &&
        alertsWs && alertsWs.readyState === WebSocket.OPEN) {
        healthChecks.websockets = true;
    }

    // Verificar gráficos
    if (document.getElementById('statusChart') && document.getElementById('resolutionChart')) {
        healthChecks.charts = true;
    }

    // Verificar filtros
    const requiredFilters = ['grupoFilter', 'colaboradorFilter', 'statusFilter', 'dataFilter'];
    healthChecks.filters = requiredFilters.every(id => document.getElementById(id));

    // Verificar dados
    const requiredMetrics = ['totalContracts', 'totalVerified', 'totalAnalysis', 'totalApproved'];
    healthChecks.data = requiredMetrics.every(id => {
        const element = document.getElementById(id);
        return element && element.textContent && element.textContent !== '0';
    });

    // Exibir status
    const healthStatus = document.getElementById('healthStatus');
    if (healthStatus) {
        let allChecksPass = Object.values(healthChecks).every(check => check);
        
        healthStatus.innerHTML = `
            <div class="health-checks mb-3">
                <h6>Status do Sistema:</h6>
                <div class="check-item">
                    <span class="${healthChecks.websockets ? 'text-success' : 'text-danger'}">
                        ${healthChecks.websockets ? '✅' : '❌'} Conexão em tempo real
                    </span>
                </div>
                <div class="check-item">
                    <span class="${healthChecks.charts ? 'text-success' : 'text-danger'}">
                        ${healthChecks.charts ? '✅' : '❌'} Gráficos
                    </span>
                </div>
                <div class="check-item">
                    <span class="${healthChecks.filters ? 'text-success' : 'text-danger'}">
                        ${healthChecks.filters ? '✅' : '❌'} Filtros
                    </span>
                </div>
                <div class="check-item">
                    <span class="${healthChecks.data ? 'text-success' : 'text-danger'}">
                        ${healthChecks.data ? '✅' : '❌'} Dados
                    </span>
                </div>
            </div>
        `;

        if (!allChecksPass) {
            console.error('Problemas detectados no frontend:', healthChecks);
        }
    }

    return Object.values(healthChecks).every(check => check);
}

// Initialize WebSocket connections
function initializeWebSockets() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsBase = `${wsProtocol}//${window.location.host}/ws`;

    // Disconnect existing connections if any
    if (metricsWs) {
        metricsWs.close();
    }
    if (alertsWs) {
        alertsWs.close();
    }

    // Connect to metrics channel
    metricsWs = new WebSocket(`${wsBase}/metrics`);
    metricsWs.onopen = () => {
        console.log('Metrics WebSocket connected');
        setLoadingState(false);
    };
    metricsWs.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateMetrics(data);
    };
    metricsWs.onclose = () => {
        console.log('Metrics WebSocket closed. Reconnecting...');
        setLoadingState(true);
        setTimeout(() => initializeWebSockets(), 2000);
    };

    // Connect to alerts channel
    alertsWs = new WebSocket(`${wsBase}/alerts`);
    alertsWs.onopen = () => {
        console.log('Alerts WebSocket connected');
    };
    alertsWs.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateAlerts(data.alerts);
    };
    alertsWs.onclose = () => {
        console.log('Alerts WebSocket closed. Reconnecting...');
        setTimeout(() => initializeWebSockets(), 2000);
    };
}

// Set loading state
function setLoadingState(loading) {
    isLoading = loading;
    const container = document.getElementById('dashboard-container');
    if (loading) {
        container.classList.add('loading');
        showLoadingIndicator();
    } else {
        container.classList.remove('loading');
        hideLoadingIndicator();
    }
}

// Show loading indicator
function showLoadingIndicator() {
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'loading-indicator';
    loadingDiv.className = 'loading-overlay';
    loadingDiv.innerHTML = `
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Carregando...</span>
        </div>
        <div class="mt-2">Carregando dados...</div>
    `;
    document.body.appendChild(loadingDiv);
}

// Hide loading indicator
function hideLoadingIndicator() {
    const loadingDiv = document.getElementById('loading-indicator');
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

// Update metrics and charts
function updateMetrics(data) {
    try {
        if (!data || !data.total_metrics) {
            console.error('Dados inválidos recebidos:', data);
            return;
        }

        setLoadingState(true);

        // Update total metrics with animation
        animateCounter('totalContracts', data.total_metrics.total_contracts);
        animateCounter('totalVerified', data.total_metrics.total_verified);
        animateCounter('totalAnalysis', data.total_metrics.total_analysis);
        animateCounter('totalApproved', data.total_metrics.total_approved);
        document.getElementById('lastUpdate').textContent = data.timestamp;

        // Update collaborator metrics
        updateCollaboratorMetrics(data);

        // Update charts
        updateCharts(data);

        // Update filter options
        updateFilterOptions();

        setLoadingState(false);

    } catch (error) {
        console.error('Erro ao atualizar métricas:', error);
        showError('Erro ao atualizar dados. Verifique o console para mais detalhes.');
        setLoadingState(false);
    }
}

// Update collaborator metrics
function updateCollaboratorMetrics(data) {
    const collaboratorMetricsContainer = document.getElementById('collaboratorMetrics');
    if (!collaboratorMetricsContainer) {
        console.error('Container de métricas não encontrado');
        return;
    }

    collaboratorMetricsContainer.innerHTML = '';
    // Reset collaborators by group
    collaboratorsByGroup = {
        'JULIO': [],
        'LEANDRO': []
    };

    if (!data.collaborator_metrics || Object.keys(data.collaborator_metrics).length === 0) {
        console.error('Dados dos colaboradores ausentes ou vazios');
        return;
    }

    // Debug log
    console.log('Dados recebidos:', data.collaborator_metrics);

    // Primeiro, vamos organizar os colaboradores por grupo
    Object.entries(data.collaborator_metrics).forEach(([collaborator, metrics]) => {
        if (metrics.grupo === 'JULIO' || metrics.grupo === 'LEANDRO') {
            collaboratorsByGroup[metrics.grupo].push(collaborator);
        }
    });

    // Debug log
    console.log('Colaboradores organizados por grupo:', collaboratorsByGroup);

    // Agora vamos criar os cards para cada grupo
    ['JULIO', 'LEANDRO'].forEach(grupo => {
        if (collaboratorsByGroup[grupo].length > 0) {
            // Criar cabeçalho do grupo
            const groupHeader = document.createElement('div');
            groupHeader.className = 'col-12 mb-3';
            groupHeader.innerHTML = `<h4 class="text-primary">Grupo ${grupo}</h4>`;
            collaboratorMetricsContainer.appendChild(groupHeader);

            // Criar cards para cada colaborador do grupo
            collaboratorsByGroup[grupo].sort().forEach(collaborator => {
                const metrics = data.collaborator_metrics[collaborator];
                const colDiv = document.createElement('div');
                colDiv.className = 'col-md-6 mb-4';
                colDiv.innerHTML = `
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0">${collaborator} (${metrics.grupo})</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-6">
                                    <div class="metric-card">
                                        <div class="metric-value">${metrics.status_counts.verified || 0}</div>
                                        <div class="metric-label">Verificados</div>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="metric-card">
                                        <div class="metric-value">${metrics.status_counts.analysis || 0}</div>
                                        <div class="metric-label">Em Análise</div>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="metric-card">
                                        <div class="metric-value">${metrics.status_counts.approved || 0}</div>
                                        <div class="metric-label">Aprovados</div>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="metric-card">
                                        <div class="metric-value">${metrics.avg_resolution_time.toFixed(1)}</div>
                                        <div class="metric-label">Tempo Médio (h)</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                collaboratorMetricsContainer.appendChild(colDiv);
            });
        }
    });

    // Debug log
    console.log('Colaboradores por grupo após atualização:', collaboratorsByGroup);
}

// Update charts
function updateCharts(data) {
    if (!data || !data.total_metrics) {
        throw new Error('Dados inválidos para atualização dos gráficos');
    }

    // Status chart
    const statusData = {
        values: [
            data.total_metrics.total_verified,
            data.total_metrics.total_analysis,
            data.total_metrics.total_approved,
            data.total_metrics.total_pending,
            data.total_metrics.total_paid,
            data.total_metrics.total_seized,
            data.total_metrics.total_priority,
            data.total_metrics.total_high_priority,
            data.total_metrics.total_cancelled,
            data.total_metrics.total_other
        ],
        labels: [
            'Verificados',
            'Em Análise',
            'Aprovados',
            'Pendentes',
            'Quitados',
            'Apreendidos',
            'Prioridade',
            'Prioridade Total',
            'Cancelados',
            'Outros'
        ],
        type: 'pie',
        hole: 0.4,
        marker: {
            colors: [
                '#198754', // verde - verificados
                '#0d6efd', // azul - análise
                '#ffc107', // amarelo - aprovados
                '#6c757d', // cinza - pendentes
                '#20c997', // verde água - quitados
                '#dc3545', // vermelho - apreendidos
                '#fd7e14', // laranja - prioridade
                '#e83e8c', // rosa - prioridade total
                '#6610f2', // roxo - cancelados
                '#adb5bd'  // cinza claro - outros
            ]
        }
    };

    const statusLayout = {
        margin: { t: 0, b: 0, l: 0, r: 0 },
        showlegend: true,
        legend: { orientation: 'h', y: -0.2 }
    };

    try {
        Plotly.newPlot('statusChart', [statusData], statusLayout);
    } catch (error) {
        console.error('Erro ao criar gráfico de status:', error);
        throw error;
    }

    // Resolution time chart
    if (!data.collaborator_metrics) {
        throw new Error('Dados de métricas dos colaboradores ausentes');
    }

    const resolutionData = {
        x: Object.keys(data.collaborator_metrics),
        y: Object.values(data.collaborator_metrics).map(m => m.avg_resolution_time),
        type: 'bar',
        marker: {
            color: '#0d6efd'
        }
    };

    const resolutionLayout = {
        margin: { t: 0, b: 40, l: 40, r: 0 },
        yaxis: { 
            title: 'Horas',
            gridcolor: '#f8f9fa'
        },
        xaxis: {
            gridcolor: '#f8f9fa'
        },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white'
    };

    try {
        Plotly.newPlot('resolutionChart', [resolutionData], resolutionLayout);
    } catch (error) {
        console.error('Erro ao criar gráfico de tempo de resolução:', error);
        throw error;
    }
}

// Update filter options based on current data
function updateFilterOptions() {
    const grupoFilter = document.getElementById('grupoFilter');
    const colaboradorFilter = document.getElementById('colaboradorFilter');
    const statusFilter = document.getElementById('statusFilter');
    const selectedGroup = grupoFilter.value;

    // Debug log
    console.log('Atualizando filtros - Grupo selecionado:', selectedGroup);
    console.log('Colaboradores disponíveis:', collaboratorsByGroup);

    // Garantir que o filtro de grupo tenha as opções corretas
    if (grupoFilter.options.length <= 1) {
        grupoFilter.innerHTML = `
            <option value="">Todos</option>
            <option value="JULIO">JULIO</option>
            <option value="LEANDRO">LEANDRO</option>
        `;
    }

    // Garantir que o filtro de status tenha as opções corretas
    if (statusFilter.options.length <= 1) {
        statusFilter.innerHTML = `
            <option value="">Todos</option>
            <option value="verified">Verificados</option>
            <option value="analysis">Em Análise</option>
            <option value="approved">Aprovados</option>
            <option value="pending">Pendentes</option>
            <option value="paid">Quitados</option>
            <option value="seized">Apreendidos</option>
            <option value="priority">Prioridade</option>
            <option value="high_priority">Prioridade Total</option>
            <option value="cancelled">Cancelados</option>
            <option value="other">Outros</option>
        `;
    }

    // Update collaborator filter
    colaboradorFilter.innerHTML = '<option value="">Todos</option>';
    
    if (selectedGroup) {
        const collaborators = collaboratorsByGroup[selectedGroup] || [];
        console.log(`Colaboradores do grupo ${selectedGroup}:`, collaborators);
        
        collaborators.sort().forEach(collaborator => {
            const option = document.createElement('option');
            option.value = collaborator;
            option.textContent = collaborator;
            colaboradorFilter.appendChild(option);
        });
    } else {
        // Show all collaborators when no group is selected
        Object.entries(collaboratorsByGroup).forEach(([group, collaborators]) => {
            collaborators.sort().forEach(collaborator => {
                const option = document.createElement('option');
                option.value = collaborator;
                option.textContent = `${collaborator} (${group})`;
                colaboradorFilter.appendChild(option);
            });
        });
    }
}

// Update alerts
function updateAlerts(alerts) {
    const container = document.getElementById('alerts-container');
    container.innerHTML = '';

    if (!alerts || alerts.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info">
                <i class="bi bi-info-circle"></i>
                Nenhum alerta ativo no momento.
            </div>
        `;
        return;
    }

    alerts.forEach(alert => {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${getAlertClass(alert.type)}`;
        alertDiv.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <i class="bi ${getAlertIcon(alert.type)}"></i>
                    ${alert.message}
                </div>
                <small class="text-muted">${formatDate(alert.created_at)}</small>
            </div>
        `;
        container.appendChild(alertDiv);
    });
}

// Helper functions
function getAlertClass(type) {
    const classes = {
        'warning': 'warning',
        'critical': 'danger',
        'info': 'info'
    };
    return classes[type] || 'info';
}

function getAlertIcon(type) {
    const icons = {
        'warning': 'bi-exclamation-triangle',
        'critical': 'bi-exclamation-circle',
        'info': 'bi-info-circle'
    };
    return icons[type] || 'bi-info-circle';
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleString('pt-BR');
}

function animateCounter(elementId, targetValue) {
    const element = document.getElementById(elementId);
    const startValue = parseInt(element.textContent) || 0;
    const duration = 1000; // 1 second
    const steps = 60;
    const stepValue = (targetValue - startValue) / steps;
    let currentStep = 0;

    const animation = setInterval(() => {
        currentStep++;
        const currentValue = Math.round(startValue + (stepValue * currentStep));
        element.textContent = currentValue;

        if (currentStep >= steps) {
            element.textContent = targetValue;
            clearInterval(animation);
        }
    }, duration / steps);
}

// Refresh data with filters
async function refreshData() {
    try {
        const refreshBtn = document.getElementById('refreshBtn');
        refreshBtn.classList.add('loading');
        setLoadingState(true);
        
        // Get filter values
        const grupo = document.getElementById('grupoFilter').value;
        const collaborator = document.getElementById('colaboradorFilter').value;
        const status = document.getElementById('statusFilter').value;
        const data = document.getElementById('dataFilter').value;
        
        // Debug log
        console.log('Refreshing data with filters:', { grupo, collaborator, status, data });
        
        // Build query string
        const params = new URLSearchParams();
        if (grupo) params.append('grupo', grupo);
        if (collaborator) params.append('collaborator', collaborator);
        if (status) params.append('status', status);
        if (data) params.append('data', data);
        
        // Make API request
        const metricsResponse = await fetch(`/api/metrics?${params.toString()}`);
        if (!metricsResponse.ok) {
            throw new Error(`HTTP error! status: ${metricsResponse.status}`);
        }
        const metricsData = await metricsResponse.json();
        
        // Debug log
        console.log('Received metrics data:', metricsData);
        
        // Verificar se os dados contêm informações de grupo
        if (metricsData.collaborator_metrics) {
            Object.entries(metricsData.collaborator_metrics).forEach(([collaborator, metrics]) => {
                // Garantir que o grupo está definido corretamente
                if (!metrics.grupo) {
                    console.warn(`Colaborador ${collaborator} sem grupo definido`);
                    
                    // Tentar inferir o grupo pelo nome do contrato
                    if (collaborator.includes('JULIO')) {
                        metrics.grupo = 'JULIO';
                    } else if (collaborator.includes('LEANDRO')) {
                        metrics.grupo = 'LEANDRO';
                    } else {
                        // Verificar se o grupo foi selecionado no filtro
                        if (grupo && (grupo === 'JULIO' || grupo === 'LEANDRO')) {
                            metrics.grupo = grupo;
                        } else {
                            metrics.grupo = 'N/A';
                        }
                    }
                    
                    console.log(`Grupo inferido para ${collaborator}: ${metrics.grupo}`);
                }
            });
        }
        
        // Update metrics and UI
        updateMetrics(metricsData);
        updateCollaboratorsTable(metricsData);
        checkFrontendHealth();
        
    } catch (error) {
        console.error('Error refreshing data:', error);
        showError('Erro ao atualizar dados. Tente novamente.');
    } finally {
        const refreshBtn = document.getElementById('refreshBtn');
        refreshBtn.classList.remove('loading');
        setLoadingState(false);
    }
}

function updateCollaboratorsTable(data) {
    const tableBody = document.querySelector('#colaboradoresTable tbody');
    if (!tableBody) return;

    tableBody.innerHTML = '';
    
    if (!data.collaborator_metrics) return;

    Object.entries(data.collaborator_metrics)
        .sort(([a], [b]) => a.localeCompare(b))
        .forEach(([collaborator, metrics]) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${collaborator}</td>
                <td>${metrics.grupo || 'N/A'}</td>
                <td>${Object.values(metrics.status_counts).reduce((a, b) => a + b, 0)}</td>
                <td>${metrics.status_counts.verified || 0}</td>
                <td>${metrics.status_counts.analysis || 0}</td>
                <td>${metrics.status_counts.approved || 0}</td>
                <td>${metrics.avg_resolution_time.toFixed(1)}h</td>
            `;
            tableBody.appendChild(row);
        });
}

function showError(message) {
    const container = document.getElementById('collaboratorMetrics');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'col-12';
    errorDiv.innerHTML = `
        <div class="alert alert-danger">
            <div class="d-flex align-items-center">
                <i class="bi bi-exclamation-circle me-2"></i>
                ${message}
            </div>
        </div>
    `;
    container.insertBefore(errorDiv, container.firstChild);
    
    // Remove error message after 5 seconds
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing dashboard...');
    initializeWebSockets();

    // Add filter change handlers
    document.getElementById('grupoFilter').addEventListener('change', (event) => {
        console.log('Grupo filter changed:', event.target.value);
        updateFilterOptions();
        refreshData();
    });
    
    document.getElementById('colaboradorFilter').addEventListener('change', () => refreshData());
    document.getElementById('statusFilter').addEventListener('change', () => refreshData());
    document.getElementById('dataFilter').addEventListener('change', () => refreshData());

    // Refresh button handler
    document.getElementById('refreshBtn').addEventListener('click', refreshData);

    // Initial data load
    refreshData();

    // Auto refresh every 30 seconds
    setInterval(refreshData, 30000);
}); 