// archive.js

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

// Функция загрузки архивных матчей
function loadArchiveMatches() {
    const dateFrom = document.getElementById('dateFrom').value;
    const dateTo = document.getElementById('dateTo').value;
    const tournament = document.getElementById('tournament').value;
    const team = document.getElementById('team').value;

    document.getElementById('matches-table').innerHTML = '<div class="loading">🔄 Загрузка архивных матчей...</div>';
    document.getElementById('stats').innerHTML = 'Загрузка...';

    let url = '/api/matches/archive?';
    const params = [];
    
    if (dateFrom) params.push(`date_from=${dateFrom}`);
    if (dateTo) params.push(`date_to=${dateTo}`);
    if (tournament) params.push(`tournament=${encodeURIComponent(tournament)}`);
    if (team) params.push(`team=${encodeURIComponent(team)}`);
    
    url += params.join('&');

    fetch(url)
        .then(response => response.json())
        .then(data => {
            updateArchiveTable(data.matches);
            updateArchiveStats(data.stats);
        })
        .catch(error => {
            console.error('Ошибка загрузки архива:', error);
            document.getElementById('matches-table').innerHTML = 
                '<div class="loading">❌ Ошибка загрузки архива</div>';
        });
}

// Функция обновления таблицы архивных матчей
function updateArchiveTable(matches) {
    if (!matches || matches.length === 0) {
        document.getElementById('matches-table').innerHTML = 
            '<div class="loading">📭 Нет матчей по выбранным фильтрам</div>';
        document.getElementById('stats').innerHTML = 
            'Матчей: 0';
        return;
    }

    document.getElementById('stats').innerHTML = 
        `📊 Найдено матчей: ${matches.length}`;

    let html = `
        <table>
            <thead>
                <tr>
                    <th>Дата</th>
                    <th>Команды / Турнир</th>
                    <th>Статус</th>
                    <th>Финальный счет</th>
                    <th>Очки</th>
                    <th>Нач. тотал</th>
                    <th>Макс. тотал</th>
                    <th>Отличие нач.→фин.</th>
                    <th>Наша ставка</th>
                </tr>
            </thead>
            <tbody>
    `;

    matches.forEach(match => {
        // Определяем статус матча
        const status = getMatchStatus(match);
        
        // Вычисляем отличие начального тотала от финального счета
        const initialFinalDiff = match.initial_total && match.final_points ? 
            match.final_points - match.initial_total : null;
        const initialFinalDiffPercent = initialFinalDiff && match.initial_total ? 
            (initialFinalDiff / match.initial_total) * 100 : null;
        
        // Класс для отличия начального тотала от финального счета
        const diffClass = initialFinalDiffPercent >= 5 ? 'positive' : 
                        initialFinalDiffPercent <= -5 ? 'negative' : 'neutral';

        // Информация о нашей ставке
        const betInfo = match.bet_total ? 
            `ТМ ${match.bet_total} (${match.triggered_at})` : 'Нет ставки';
        
        const resultClass = match.bet_result === 'WIN' ? 'positive' : 
                          match.bet_result === 'LOSE' ? 'negative' : 'neutral';

        html += `
            <tr onclick="showArchiveChart(${match.id}, '${escapeHtml(match.teams)}')" style="cursor: pointer;">
                <td>${match.finished_date || '-'}</td>
                <td>
                    <div class="match-teams">${match.teams}</div>
                    <div class="tournament">${match.tournament}</div>
                </td>
                <td>
                    <span class="${status.class}">
                        ${status.text}
                    </span>
                </td>
                <td><strong>${match.final_score || match.score || '-'}</strong></td>
                <td><strong>${match.final_points || match.total_points || '-'}</strong></td>
                <td>${match.initial_total || '-'}</td>
                <td>${match.final_total || match.total_value || '-'}</td>
                <td>
                    <span class="${diffClass}">
                        ${initialFinalDiff !== null ? 
                            `${initialFinalDiff > 0 ? '+' : ''}${initialFinalDiff.toFixed(1)} 
                             (${initialFinalDiffPercent > 0 ? '+' : ''}${initialFinalDiffPercent.toFixed(1)}%)` 
                            : '-'
                        }
                    </span>
                </td>
                <td>
                    <div style="font-size: 12px; color: #7f8c8d; margin-bottom: 3px;">
                        ${betInfo}
                    </div>
                    <span class="${resultClass}">
                        ${match.bet_result || 'Нет ставки'}
                    </span>
                </td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    document.getElementById('matches-table').innerHTML = html;
}

// Функция определения статуса матча
function getMatchStatus(match) {
    // Если есть статус 'finished' - матч завершен
    if (match.status === 'finished') {
        return {
            text: '✅ Завершен',
            class: 'positive'
        };
    }
    
    // Если есть статус 'active' - активный матч
    if (match.status === 'active') {
        return {
            text: '🟡 Активный',
            class: 'neutral'
        };
    }
    
    // Если нет статуса, но есть время матча - проверяем по времени
    if (match.current_time && match.total_match_time) {
        const minutesElapsed = calculateMinutesElapsed(match.current_time);
        const totalMinutes = match.total_match_time;
        
        // Если время матча близко к полному - считаем завершенным
        if (minutesElapsed >= totalMinutes - 1) {
            return {
                text: '✅ Завершен',
                class: 'positive'
            };
        } else {
            return {
                text: '🟡 Активный',
                class: 'neutral'
            };
        }
    }
    
    // Если ничего не известно - неизвестный статус
    return {
        text: '❓ Неизвестно',
        class: 'neutral'
    };
}

// Функция расчета минут матча (добавляем если нет в utils.js)
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

// Функция обновления статистики архива
function updateArchiveStats(stats) {
    if (!stats) return;
    
    document.getElementById('totalMatches').textContent = stats.total_matches || '-';
    document.getElementById('overPercentage').textContent = stats.over_percentage ? stats.over_percentage + '%' : '-';
    document.getElementById('underPercentage').textContent = stats.under_percentage ? stats.under_percentage + '%' : '-';
    document.getElementById('avgDeviation').textContent = stats.avg_deviation ? stats.avg_deviation + '%' : '-';
}

function showArchiveChart(matchId, teams) {
    console.log('📊 Opening archive chart for match:', matchId);
    
    currentOpenMatchId = matchId;
    
    fetch(`/api/matches/${matchId}/chart`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                return;
            }
            
            const finalInfo = data.final_result ? 
                ` | Финальный результат: ${data.final_result}` : '';
            
            document.getElementById('chartTitle').innerHTML = `
                <div style="text-align: center; padding: 10px 0;">
                    <div style="font-size: 20px; font-weight: bold; color: #2c3e50; margin-bottom: 6px;">
                        ${teams} ${finalInfo}
                    </div>
                    <div style="font-size: 14px; color: #7f8c8d; background: #f8f9fa; padding: 4px 12px; border-radius: 12px; display: inline-block;">
                        📊 Архивный матч
                    </div>
                </div>
            `;
            
            // ИСПОЛЬЗУЕМ СУЩЕСТВУЮЩУЮ ФУНКЦИЮ ИЗ chart.js
            createChart(data, teams, 'Архивный матч', '');
            modal.style.display = 'block';
        })
        .catch(error => {
            console.error('Ошибка загрузки графика:', error);
            alert('Ошибка загрузки графика');
        });
}


// Функция получения текущих значений для легенды
function getCurrentValues(chartData) {
    if (!chartData || !chartData.total_points || chartData.total_points.length === 0) {
        return { totalPoints: '-', totalValue: '-', pace: '-' };
    }
    
    const lastIndex = chartData.total_points.length - 1;
    
    return {
        totalPoints: chartData.total_points[lastIndex] || '-',
        totalValue: chartData.total_values[lastIndex] || '-',
        pace: chartData.pace_data[lastIndex] || '-'
    };
}

// Вспомогательные функции
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getDeviationClass(deviation) {
    if (!deviation) return 'neutral';
    if (deviation > 5) return 'positive';
    if (deviation < -5) return 'negative';
    return 'neutral';
}

// Загрузка архива при открытии страницы
document.addEventListener('DOMContentLoaded', function() {
    loadArchiveMatches();
    
    // Устанавливаем даты по умолчанию (последние 7 дней)
    const today = new Date();
    const weekAgo = new Date();
    weekAgo.setDate(today.getDate() - 7);
    
    document.getElementById('dateFrom').value = weekAgo.toISOString().split('T')[0];
    document.getElementById('dateTo').value = today.toISOString().split('T')[0];
});