// utils.js - общие утилиты для всего приложения

// Глобальные переменные
var currentChart = null;
var wsConnected = false;
var currentOpenMatchId = null;
var previousChartData = null;
var changeIndicatorTimeout = null;

// Конфигурация ставок
const BET_CONFIG = {
    WARNING_PERCENT: 10
};

// ==================== ОБЩИЕ УТИЛИТЫ ====================

// Экранирование HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Расчет минут из времени формата "MM:SS"
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

// Конвертация времени в минуты (для графиков)
function timeToMinutes(timeStr) {
    if (!timeStr || timeStr === '-') return 0;
    
    // Убираем возможные лишние символы
    timeStr = timeStr.trim().split(' ')[0];
    
    const parts = timeStr.split(':');
    const minutes = parseInt(parts[0]) || 0;
    const seconds = parseInt(parts[1]) || 0;
    const result = minutes + (seconds / 60);
    return result;
}

// ==================== ЦВЕТОВЫЕ КЛАССЫ ====================

function getDeviationClass(deviation) {
    if (!deviation) return 'neutral';
    if (deviation > 5) return 'positive';
    if (deviation < -5) return 'negative';
    return 'neutral';
}

function getTotalDiffClass(diff, percent) {
    if (!diff || diff === 0) return '';
    
    if (percent < -BET_CONFIG.WARNING_PERCENT) return 'row-negative';
    if (percent > BET_CONFIG.WARNING_PERCENT) return 'row-positive';
    return '';
}

function getCellDiffClass(percent) {
    if (!percent) return 'neutral';
    if (percent < -10) return 'negative';
    if (percent > 10) return 'positive';
    return 'neutral';
}

// ==================== РАБОТА С ДАННЫМИ МАТЧЕЙ ====================

// Получение информации о матче по ID
function getMatchInfoByMatchId(matchId) {
    console.log('🔍 Поиск информации о матче:', matchId);
    
    // Используем window.currentMatchInfo, если он соответствует текущему матчу
    if (window.currentMatchInfo && window.currentMatchInfo.matchId === matchId) {
        console.log('✅ Используем window.currentMatchInfo:', window.currentMatchInfo);
        return window.currentMatchInfo;
    }
    
    // Поиск в DOM среди активных матчей
    const rows = document.querySelectorAll('#matches-table tbody tr');
    for (let row of rows) {
        const onclickAttr = row.getAttribute('onclick');
        if (onclickAttr && onclickAttr.includes(`showMatchChart(${matchId},`)) {
            const matchTeams = row.querySelector('.match-teams');
            const tournamentElement = row.querySelector('.tournament');
            const timeElement = row.querySelector('td:nth-child(2) strong');
            
            const matchInfo = {
                matchId: matchId,
                teams: matchTeams ? matchTeams.textContent : 'Неизвестные команды',
                tournament: tournamentElement ? tournamentElement.textContent : 'Неизвестный турнир',
                currentTime: timeElement ? timeElement.textContent : '-'
            };
            
            console.log('✅ Найдено в активных матчах:', matchInfo);
            return matchInfo;
        }
    }
    
    // Поиск в DOM среди архивных матчей
    for (let row of rows) {
        const onclickAttr = row.getAttribute('onclick');
        if (onclickAttr && onclickAttr.includes(`showArchiveChart(${matchId},`)) {
            const matchTeams = row.querySelector('.match-teams');
            const tournamentElement = row.querySelector('.tournament');
            const timeElement = row.querySelector('td:nth-child(4) strong');
            
            const matchInfo = {
                matchId: matchId,
                teams: matchTeams ? matchTeams.textContent : 'Неизвестные команды',
                tournament: tournamentElement ? tournamentElement.textContent : 'Архивный матч',
                currentTime: timeElement ? timeElement.textContent : 'Завершен'
            };
            
            console.log('✅ Найдено в архивных матчах:', matchInfo);
            return matchInfo;
        }
    }
    
    console.log('❌ Матч не найден в DOM, используем значения по умолчанию');
    return {
        matchId: matchId,
        teams: 'Команда 1 vs Команда 2',
        tournament: 'Турнир',
        currentTime: '0:00'
    };
}

// ==================== ИНДИКАТОРЫ ИЗМЕНЕНИЙ ====================

function updateDiffElement(element, diff) {
    const absDiff = Math.abs(diff);
    
    if (diff > 0) {
        element.textContent = `+${absDiff.toFixed(1)}`;
        element.className = 'change-diff positive';
    } else if (diff < 0) {
        element.textContent = `-${absDiff.toFixed(1)}`;
        element.className = 'change-diff negative';
    } else {
        element.textContent = '0.0';
        element.className = 'change-diff neutral';
    }
}

function updateChangeIndicator(changes) {
    const indicator = document.getElementById('changeIndicator');
    const pointsElem = document.getElementById('changePoints');
    const paceElem = document.getElementById('changePace');
    const totalElem = document.getElementById('changeTotal');
    const pointsDiffElem = document.getElementById('changePointsDiff');
    const paceDiffElem = document.getElementById('changePaceDiff');
    const totalDiffElem = document.getElementById('changeTotalDiff');
    
    if (!indicator) return;
    
    pointsElem.textContent = changes.points.value.toFixed(1);
    paceElem.textContent = changes.pace.value.toFixed(1);
    totalElem.textContent = changes.total.value.toFixed(1);
    
    updateDiffElement(pointsDiffElem, changes.points.diff);
    updateDiffElement(paceDiffElem, changes.pace.diff);
    updateDiffElement(totalDiffElem, changes.total.diff);
    
    indicator.classList.add('show');
    
    if (changeIndicatorTimeout) {
        clearTimeout(changeIndicatorTimeout);
    }
    
    changeIndicatorTimeout = setTimeout(() => {
        indicator.classList.remove('show');
    }, 5000);
}

function showChangesIndicator(newData) {
    if (!previousChartData || !newData.timestamps || newData.timestamps.length === 0) {
        previousChartData = JSON.parse(JSON.stringify(newData));
        return;
    }
    
    const newIndex = newData.timestamps.length - 1;
    const oldIndex = previousChartData.timestamps.length - 1;
    
    if (oldIndex < 0 || newIndex < 0) {
        previousChartData = JSON.parse(JSON.stringify(newData));
        return;
    }
    
    if (newData.timestamps[newIndex] === previousChartData.timestamps[oldIndex]) {
        return;
    }
    
    const newPoints = newData.total_points[newIndex] || 0;
    const newPace = newData.pace_data[newIndex] || 0;
    const newTotal = newData.total_values[newIndex] || 0;
    
    const oldPoints = previousChartData.total_points[oldIndex] || 0;
    const oldPace = previousChartData.pace_data[oldIndex] || 0;
    const oldTotal = previousChartData.total_values[oldIndex] || 0;
    
    const pointsDiff = newPoints - oldPoints;
    const paceDiff = newPace - oldPace;
    const totalDiff = newTotal - oldTotal;
    
    if (Math.abs(pointsDiff) > 0.1 || Math.abs(paceDiff) > 0.1 || Math.abs(totalDiff) > 0.1) {
        updateChangeIndicator({
            points: { value: newPoints, diff: pointsDiff },
            pace: { value: newPace, diff: paceDiff },
            total: { value: newTotal, diff: totalDiff }
        });
    }
    
    previousChartData = JSON.parse(JSON.stringify(newData));
}

// ==================== МОДАЛЬНЫЕ ОКНА ====================

// Закрытие модального окна графика
function closeChartModal() {
    const modal = document.getElementById('chartModal');
    if (modal) {
        modal.style.display = 'none';
    }
    if (currentChart) {
        currentChart.destroy();
        currentChart = null;
    }
    currentOpenMatchId = null;
}

// Инициализация обработчиков модального окна
function initModalHandlers() {
    const modal = document.getElementById('chartModal');
    const closeBtn = document.querySelector('.close');
    
    if (closeBtn) {
        closeBtn.onclick = closeChartModal;
    }
    
    if (modal) {
        window.onclick = function(event) {
            if (event.target == modal) {
                closeChartModal();
            }
        }
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
    initModalHandlers();
});