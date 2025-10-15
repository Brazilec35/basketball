// Глобальные переменные
let currentChart = null;
let wsConnected = false;
window.wsConnected = false;
let currentOpenMatchId = null;
let previousChartData = null;
let changeIndicatorTimeout = null;

// Обработчики для модального окна
const modal = document.getElementById('chartModal');
const closeBtn = document.querySelector('.close');

closeBtn.onclick = function() {
    modal.style.display = 'none';
    if (currentChart) {
        currentChart.destroy();
        currentChart = null;
    }
    currentOpenMatchId = null;
}

window.onclick = function(event) {
    if (event.target == modal) {
        modal.style.display = 'none';
        if (currentChart) {
            currentChart.destroy();
            currentChart = null;
        }
        currentOpenMatchId = null;
    }
}

// Вспомогательные функции
function calculateMinutesElapsed(currentTime) {
    if (!currentTime || currentTime === '-') return 0;
    try {
        const parts = currentTime.split(':');
        if (parts.length < 2) return 0;
        const minutes = parseInt(parts[0]) || 0;
        const seconds = parseInt(parts[1]) || 0;
        return minutes + (seconds / 60);
    } catch (error) {
        return 0;
    }
}

function getDeviationClass(deviation) {
    if (!deviation) return 'neutral';
    if (deviation > 5) return 'positive';
    if (deviation < -5) return 'negative';
    return 'neutral';
}

function getTotalDiffClass(diff, percent) {
    if (!diff || diff === 0) return '';
    if (percent < -10) return 'row-negative';
    if (percent > 10) return 'row-positive';
    return '';
}

function getCellDiffClass(percent) {
    if (!percent) return 'neutral';
    if (percent < -10) return 'negative';
    if (percent > 10) return 'positive';
    return 'neutral';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Функция обновления таблицы матчей
function updateTable(matches) {
    console.log('🔄 updateTable called with', matches?.length, 'matches');
    
    if (!matches || matches.length === 0) {
        document.getElementById('matches-table').innerHTML = 
            '<div class="loading">📭 Нет активных матчей в данный момент</div>';
        document.getElementById('stats').innerHTML = 
            'Матчей: 0 | Обновлено: ' + new Date().toLocaleTimeString();
        return;
    }

    document.getElementById('stats').innerHTML = 
        `📊 Матчей: ${matches.length} | 🔄 ${new Date().toLocaleTimeString()}`;
    
    const sortedMatches = [...matches].sort((a, b) => {
        return (a.tournament || 'Без турнира').localeCompare(b.tournament || 'Без турнира');
    });
    
    let html = `
        <table>
            <thead>
                <tr>
                    <th>Команды / Турнир</th>
                    <th>Время</th>
                    <th>Счет</th>
                    <th>Очки</th>
                    <th>Нач. тотал</th>
                    <th>Тек. тотал</th>
                    <th>Δ Тотала</th>
                    <th>Темп</th>
                    <th>Отклонение</th>
                </tr>
            </thead>
            <tbody>
    `;

    sortedMatches.forEach(match => {
        if (!match.minutes_elapsed && match.current_time && match.current_time !== '-') {
            match.minutes_elapsed = calculateMinutesElapsed(match.current_time);
        }
        
        const deviationClass = getDeviationClass(match.total_deviation);
        
        html += `
            <tr class="${match.initial_total && match.total_value ? getTotalDiffClass(match.total_value - match.initial_total, ((match.total_value - match.initial_total) / match.initial_total * 100)) : ''}" onclick="showMatchChart(${match.id}, '${escapeHtml(match.teams)}')">
                <td>
                    <div class="match-teams">${match.teams}</div>
                    <div class="tournament">${match.tournament}</div>
                </td>
                <td><strong>${match.current_time}</strong></td>
                <td><strong>${match.score}</strong></td>
                <td>${match.total_points}</td>
                <td>${match.initial_total || '-'}</td>
                <td>${match.total_value || '-'}</td>
                <td>
                    ${match.initial_total && match.total_value ? 
                        `<span class="${getCellDiffClass((match.total_value - match.initial_total) / match.initial_total * 100)}">
                            ${(match.total_value - match.initial_total).toFixed(1)} 
                            (${((match.total_value - match.initial_total) / match.initial_total * 100).toFixed(1)}%)
                        </span>` 
                        : '-'
                    }
                </td>                      
                <td>${match.current_pace || '-'}</td>
                <td>
                    <span class="${deviationClass}">
                        ${match.total_deviation ? `${match.total_deviation > 0 ? '+' : ''}${match.total_deviation}%` : '-'}
                    </span>
                </td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    document.getElementById('matches-table').innerHTML = html;
}

// WebSocket соединение
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    const socket = new WebSocket(wsUrl);
    
    socket.onopen = function() {
        console.log('✅ WebSocket connected');
        wsConnected = true;
        window.wsConnected = true;
        document.getElementById('stats').innerHTML = '🟢 Подключено | Ожидание данных...';
    };
    
    socket.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            if (data.type === "table_update") {
                updateTable(data.data.matches);
                updateOpenChart(data.data.matches);
            }
        } catch (error) {
            console.error('❌ Error parsing WebSocket message:', error);
        }
    };

    socket.onclose = function() {
        console.log('❌ WebSocket disconnected');
        wsConnected = false;
        window.wsConnected = false;
        document.getElementById('stats').innerHTML = '🟡 Переподключение...';
        setTimeout(connectWebSocket, 5000);
    };

    socket.onerror = function(error) {
        console.error('❌ WebSocket error:', error);
    };
}

// Остальной код (функции для графиков и индикаторов)...
// [Здесь должен быть остальной код из предыдущих файлов]

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    fetch('/api/matches')
        .then(response => response.json())
        .then(data => updateTable(data.matches))
        .catch(error => {
            console.error('❌ Initial load error:', error);
            document.getElementById('matches-table').innerHTML = 
                '<div class="loading">❌ Ошибка загрузки данных</div>';
        });

    connectWebSocket();
});