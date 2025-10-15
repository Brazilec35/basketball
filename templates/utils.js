// Глобальные переменные
let currentChart = null;
let wsConnected = false;
window.wsConnected = false;
let currentOpenMatchId = null;
let previousChartData = null;
let changeIndicatorTimeout = null;

// Функция расчета минут матча из времени
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

// Функции для цветовых классов
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

// Экранирование HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Функция для получения информации о матче
function getMatchInfoByMatchId(matchId) {
    const rows = document.querySelectorAll('#matches-table tbody tr');
    for (let row of rows) {
        const onclickAttr = row.getAttribute('onclick');
        if (onclickAttr && onclickAttr.includes(`showMatchChart(${matchId},`)) {
            const matchTeams = row.querySelector('.match-teams');
            const tournamentElement = row.querySelector('.tournament');
            const timeElement = row.querySelector('td:nth-child(2) strong');
            const scoreElement = row.querySelector('td:nth-child(3) strong');
            
            return {
                tournament: tournamentElement ? tournamentElement.textContent : 'Неизвестный турнир',
                currentTime: timeElement ? timeElement.textContent : '-',
                teams: matchTeams ? matchTeams.textContent : 'Неизвестные команды',
                score: scoreElement ? scoreElement.textContent : '-'
            };
        }
    }
    
    return {
        tournament: 'Неизвестный турнир',
        currentTime: '-',
        teams: 'Неизвестные команды',
        score: '-'
    };
}

// Функции для работы с индикатором изменений
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

// Функции для ставок
function getBetDisplay(betRecommendation) {
    if (!betRecommendation) return '';
    
    if (betRecommendation.type === 'UNDER') {
        const status = betRecommendation.status === 'confirmed' ? '✓' : '...';
        return `ТМ ${status}`;
    }
    
    return '';
}

function getBetClass(betRecommendation) {
    if (!betRecommendation) return '';
    
    if (betRecommendation.type === 'UNDER') {
        return betRecommendation.status === 'confirmed' ? 'bet-confirmed' : 'bet-pending';
    }
    
    return '';
}