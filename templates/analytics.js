// analytics.js
let statsChart = null;

// Загрузка данных при открытии страницы
document.addEventListener('DOMContentLoaded', function() {
    loadAnalyticsData();
    setInterval(loadAnalyticsData, 30000); // Обновление каждые 30 сек
});

async function loadAnalyticsData() {
    try {
        // Загружаем статистику
        const statsResponse = await fetch('/api/analytics/stats');
        const statsData = await statsResponse.json();
        
        // Загружаем историю
        const historyResponse = await fetch('/api/analytics/history?limit=100');
        const historyData = await historyResponse.json();
        
        // Обновляем интерфейс
        updateStatsCards(statsData);
        updateBetHistory(historyData.history);
        
    } catch (error) {
        console.error('Ошибка загрузки аналитики:', error);
    }
}

function updateStatsCards(stats) {
    const container = document.getElementById('statsCards');  // ← ДОБАВЬ ЭТУ СТРОКУ
    
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
                    <th>Матч</th>
                    <th>Турнир</th>
                    <th>Финальный счет</th>
                    <th>ТМ</th>
                    <th>Результат</th>
                    <th>Разница тоталов</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    history.forEach(bet => {
        const resultClass = bet.bet_result === 'WIN' ? 'positive' : 'negative';
        
        html += `
            <tr>
                <td>${bet.teams}</td>
                <td>${bet.tournament}</td>
                <td><strong>${bet.final_score}</strong> (${bet.final_points} очков)</td>
                <td>${bet.bet_total}</td>
                <td><span class="${resultClass}">${bet.bet_result}</span></td>
                <td><span class="${bet.total_diff_percent > 0 ? 'positive' : 'neutral'}">
                    ${bet.total_diff > 0 ? '+' : ''}${bet.total_diff.toFixed(1)} 
                    (${bet.total_diff_percent > 0 ? '+' : ''}${bet.total_diff_percent}%)
                </span></td>
            </tr>
        `;
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
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
        
        // Перезагружаем данные
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