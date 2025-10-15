<!-- app.js-->
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

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Первоначальная загрузка данных
    fetch('/api/matches')
        .then(response => response.json())
        .then(data => updateTable(data.matches))
        .catch(error => {
            console.error('❌ Initial load error:', error);
            document.getElementById('matches-table').innerHTML = 
                '<div class="loading">❌ Ошибка загрузки данных</div>';
        });

    // Подключаем WebSocket для live-обновлений
    connectWebSocket();
});