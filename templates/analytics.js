// analytics.js

// Загрузка данных при открытии страницы
document.addEventListener('DOMContentLoaded', function() {
    loadAnalyticsData();
    setInterval(loadAnalyticsData, 30000);
});

async function loadAnalyticsData() {
    try {
        const statsResponse = await fetch('/api/analytics/stats');
        const statsData = await statsResponse.json();
        
        const historyResponse = await fetch('/api/analytics/history?limit=100');
        const historyData = await historyResponse.json();
        
        // Сохраняем конфиг глобально
        window.TRIGGER_PERCENT = historyData.config?.trigger_percent || 12;
        
        updateStatsCards(statsData);
        updateBetHistory(historyData.history);
        
    } catch (error) {
        console.error('Ошибка загрузки аналитики:', error);
    }
}

function updateStatsCards(stats) {
    const container = document.getElementById('statsCards');
    
    if (stats.total_bets === 0) {
        container.innerHTML = '<div class="loading">📭 Нет данных для анализа</div>';
        return;
    }
    
    container.innerHTML = `
        <div class="stat-card">
            <div class="stat-value">${stats.total_bets}</div>
            <div class="stat-label">Всего ставок</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.win_rate}%</div>
            <div class="stat-label">Точность</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.wins}</div>
            <div class="stat-label">WIN</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.losses}</div>
            <div class="stat-label">LOSE</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.avg_total_diff}%</div>
            <div class="stat-label">Ср. разница</div>
        </div>
    `;
}

function updateBetHistory(history) {
    const container = document.getElementById('betHistory');
    
    if (!history || history.length === 0) {
        container.innerHTML = '<div class="loading">📭 Нет завершенных ставок</div>';
        return;
    }
    
    let html = `
        <table>
            <thead>
                <tr>
                    <th>Команды / Турнир</th>
                    <th>Финальный счет</th>
                    <th>ТМ / Время ставки</th>
                    <th>Результат</th>
                    <th>Разница тоталов</th>
                    <th>Нач. тотал → Фин.</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    history.forEach(bet => {
        const resultClass = bet.bet_result === 'WIN' ? 'positive' : 'negative';
        
        const triggerPercent = window.TRIGGER_PERCENT || 12;
        const initialFinalClass = bet.initial_final_diff_percent > triggerPercent ? 'negative' : 
                                 bet.initial_final_diff_percent > 0 ? 'positive' : 'neutral';

        html += `
            <tr onclick="showMatchChartFromAnalytics(${bet.match_id}, '${bet.teams.replace(/'/g, "\\'")}')" style="cursor: pointer;">
                <td>
                    <div class="match-teams">${bet.teams}</div>
                    <div class="tournament">${bet.tournament}</div>
                </td>
                <td>
                    <div class="score-main">${bet.final_score}</div>
                    <div class="score-details">${bet.final_points} очков</div>
                </td>
                <td>
                    <div class="bet-main">${bet.bet_total}</div>
                    <div class="bet-details">${formatBetTime(bet.triggered_at)}</div>
                </td>
                <td><span class="${resultClass}">${bet.bet_result}</span></td>
                <td><span class="${bet.total_diff_percent > 0 ? 'positive' : 'neutral'}">
                    ${bet.total_diff > 0 ? '+' : ''}${bet.total_diff.toFixed(1)} 
                    (${bet.total_diff_percent > 0 ? '+' : ''}${bet.total_diff_percent}%)
                </span></td>
                <td>
                    <div class="comparison-main">${bet.initial_total?.toFixed(1) || '-'} → ${bet.final_points}</div>
                    <span class="${initialFinalClass} comparison-details">
                        ${bet.initial_final_diff > 0 ? '+' : ''}${bet.initial_final_diff?.toFixed(1) || '0'} 
                        (${bet.initial_final_diff_percent > 0 ? '+' : ''}${bet.initial_final_diff_percent?.toFixed(1) || '0'}%)
                    </span>
                </td>
            </tr>
        `;
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

// Функция форматирования времени ставки
function formatBetTime(timestamp) {
    if (!timestamp) return '-';
    
    // Если время в формате матча (например "15:25")
    if (timestamp.includes(':')) {
        return timestamp;
    }
    
    // Если это полная дата-время
    try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('ru-RU', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    } catch (e) {
        return timestamp;
    }
}

async function rescanMatches() {
    const button = event.target;
    const originalText = button.textContent;
    button.textContent = '⏳ Проверяем...';
    button.disabled = true;
    
    try {
        const response = await fetch('/api/analytics/rescan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await response.json();
        
        document.getElementById('rescanResult').innerHTML = `
            <div class="success-message">
                ✅ ${result.message || 'Готово!'}
            </div>
        `;
        
        setTimeout(loadAnalyticsData, 1000);
        
    } catch (error) {
        document.getElementById('rescanResult').innerHTML = `
            <div class="error-message">
                ❌ Ошибка: ${error.message}
            </div>
        `;
    } finally {
        button.textContent = originalText;
        button.disabled = false;
    }
}

function showMatchChartFromAnalytics(matchId, teams) {
    window.currentOpenMatchId = matchId;
    
    fetch(`/api/matches/${matchId}/chart`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                return;
            }
            
            // УБЕДИСЬ ЧТО chart.js ЗАГРУЖЕН И ФУНКЦИЯ ДОСТУПНА
            if (typeof window.createChart === 'function') {
                window.createChart(data, teams, '', '');
                document.getElementById('chartModal').style.display = 'block';
            } else {
                console.error('Функция createChart не найдена');
                alert('Ошибка: график недоступен');
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки графика:', error);
            alert('Ошибка загрузки графика');
        });
}