<!-- chart.js-->

// Глобальные переменные для графика
var currentChart = null;
var currentOpenMatchId = null;
var previousChartData = null;
var changeIndicatorTimeout = null;
// ==================== ТЕПЛОВАЯ КАРТА ====================

// Функция расчета очков за каждую минуту
function calculatePointsPerMinute(chartData) {
    if (!chartData || !chartData.timestamps || !chartData.total_points) {
        return [];
    }
    
    try {
        const pointsPerMinute = [];
        const minutesData = {};
        
        // Находим максимальную минуту матча
        let maxMinute = 0;
        chartData.timestamps.forEach((timestamp, index) => {
            if (!timestamp || timestamp === '-' || !timestamp.includes(':')) return;
            
            const timeParts = timestamp.split(':');
            const minute = parseInt(timeParts[0]) || 0;
            const points = chartData.total_points[index] || 0;
            
            // Обновляем максимальную минуту
            maxMinute = Math.max(maxMinute, minute);
            
            if (!minutesData[minute]) {
                minutesData[minute] = {
                    points: points,
                    timestamp: timestamp
                };
            } else {
                minutesData[minute].points = Math.max(minutesData[minute].points, points);
            }
        });
        
        // 🔥 ОГРАНИЧИВАЕМ ДО ТЕКУЩЕГО ВРЕМЕНИ + небольшой запас
        const maxTime = Math.min(maxMinute + 2, 60); // Максимум 60 минут
        
        // Вычисляем очки за каждую минуту только до текущего времени
        let previousPoints = 0;
        for (let minute = 0; minute <= maxTime; minute++) {
            if (minutesData[minute]) {
                const currentPoints = minutesData[minute].points;
                const pointsThisMinute = currentPoints - previousPoints;
                
                const validPoints = Math.max(0, pointsThisMinute);
                
                pointsPerMinute.push({
                    minute: minute,
                    points: validPoints,
                    timestamp: minutesData[minute].timestamp
                });
                
                previousPoints = currentPoints;
            } else {
                pointsPerMinute.push({
                    minute: minute,
                    points: 0,
                    timestamp: `${minute}:00`
                });
            }
        }
        
        return pointsPerMinute;
    } catch (error) {
        console.error('Ошибка расчета очков за минуту:', error);
        return [];
    }
}

// Функция определения цвета по количеству очков
function getHeatmapColor(points) {
    // Защита от undefined/null
    if (points === undefined || points === null) {
        return 'rgba(100, 150, 255, 0.3)'; // Синий по умолчанию
    }
    
    points = Number(points); // Убедимся что это число
    
    if (points === 0) return 'rgba(100, 150, 255, 0.3)';      // Синий - нет очков
    if (points <= 2) return 'rgba(100, 200, 100, 0.5)';      // Зеленый - низкая
    if (points <= 4) return 'rgba(255, 255, 100, 0.6)';      // Желтый - средняя
    if (points <= 6) return 'rgba(255, 165, 0, 0.7)';        // Оранжевый - высокая
    return 'rgba(255, 50, 50, 0.8)';                         // Красный - очень высокая
}
// Функция получения градиента для тепловой карты

function getHeatmapGradient(ctx, chartArea, points) {
    // Если нет контекста или области графика, возвращаем простой цвет
    if (!ctx || !chartArea) {
        return getHeatmapColor(points);
    }
    
    try {
        const gradient = ctx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
        
        if (points === 0) {
            gradient.addColorStop(0, 'rgba(100, 150, 255, 0.1)');
            gradient.addColorStop(1, 'rgba(100, 150, 255, 0.3)');
        } else if (points <= 2) {
            gradient.addColorStop(0, 'rgba(100, 200, 100, 0.2)');
            gradient.addColorStop(1, 'rgba(100, 200, 100, 0.5)');
        } else if (points <= 4) {
            gradient.addColorStop(0, 'rgba(255, 255, 100, 0.3)');
            gradient.addColorStop(1, 'rgba(255, 255, 100, 0.6)');
        } else if (points <= 6) {
            gradient.addColorStop(0, 'rgba(255, 165, 0, 0.4)');
            gradient.addColorStop(1, 'rgba(255, 165, 0, 0.7)');
        } else {
            gradient.addColorStop(0, 'rgba(255, 50, 50, 0.5)');
            gradient.addColorStop(1, 'rgba(255, 50, 50, 0.8)');
        }
        
        return gradient;
    } catch (error) {
        // Если возникла ошибка, возвращаем простой цвет
        return getHeatmapColor(points);
    }
}

// Функция создания данных для тепловой карты
function createHeatmapData(chartData) {
    try {
        const pointsPerMinute = calculatePointsPerMinute(chartData);
        const heatmapData = [];
        
        pointsPerMinute.forEach(item => {
            heatmapData.push({
                x: item.minute,
                y: item.points * 10,
                points: item.points,
                timestamp: item.timestamp
            });
        });
        
        return heatmapData;
    } catch (error) {
        console.error('Ошибка создания тепловой карты:', error);
        return [];
    }
}

// Функция проверки доступности данных для тепловой карты
function isHeatmapDataAvailable(chartData) {
    return chartData && 
        chartData.timestamps && 
        chartData.timestamps.length > 0 && 
        chartData.total_points && 
        chartData.total_points.length > 0;
}
// Функции для обновления легенды графика
function updateLegendLabels(chart) {
    const datasets = chart.data.datasets;
    return datasets.map((dataset, index) => {
        let label = dataset.originalLabel || dataset.label || '';
        
        // Специальная обработка для тепловой карты
        if (label.includes('Тепловая карта')) {
            return {
                text: '🔥 ' + label,
                fillStyle: 'rgba(255, 100, 100, 0.6)',
                strokeStyle: 'rgba(255, 100, 100, 1)',
                lineWidth: 2,
                pointStyle: 'rect',
                hidden: !chart.isDatasetVisible(index),
                index: index
            };
        }
        
        return {
            text: label,
            fillStyle: dataset.borderColor,
            strokeStyle: dataset.borderColor,
            lineWidth: 2,
            pointStyle: dataset.pointStyle,
            hidden: !chart.isDatasetVisible(index),
            index: index
        };
    });
}

function timeToMinutes(timeStr) {

    if (!timeStr || timeStr === '-') return 0;
    
    // Убираем возможные лишние символы
    timeStr = timeStr.trim().split(' ')[0]; // Берем только часть до пробела
    
    const parts = timeStr.split(':');
    const minutes = parseInt(parts[0]) || 0;
    const seconds = parseInt(parts[1]) || 0;
    const result = minutes + (seconds / 60);
    return result;
}

function updateDatasetLabels(chart) {
    if (!chart || !chart.data || !chart.data.datasets) return;
    
    chart.data.datasets.forEach((dataset, index) => {
        dataset.label = dataset.originalLabel || dataset.label || '';
    });
}

// Функции для графика
function refreshChart(newData) {
    if (!currentChart || !newData.timestamps) return;
    
    window.currentChartData = newData;
    
    // Конвертируем временные метки в минуты для оси X
    const xValues = newData.timestamps.map(timeToMinutes);
    
    const totalValues = newData.total_values.filter(val => val !== null && val !== undefined);
    const maxTotal = totalValues.length > 0 ? Math.max(...totalValues) : null;
    const minTotal = totalValues.length > 0 ? Math.min(...totalValues) : null;
    
    // 🔥 ОБНОВЛЯЕМ ДАННЫЕ ТЕПЛОВОЙ КАРТЫ
    if (currentChart.data.datasets[0] && currentChart.data.datasets[0].label.includes('Тепловая карта')) {
        currentChart.data.datasets[0].data = createHeatmapData(newData);
        
        // 🔥 ОБНОВЛЯЕМ МАКСИМУМ ОСИ X на основе последней временной метки
        if (newData.timestamps && newData.timestamps.length > 0) {
            const lastTimestamp = newData.timestamps[newData.timestamps.length - 1];
            if (lastTimestamp && lastTimestamp.includes(':')) {
                const lastMinute = parseInt(lastTimestamp.split(':')[0]) || 0;
                currentChart.options.scales.x.max = Math.min(lastMinute + 1, newData.total_match_time || 48);
            }
        }
    }
    
    // Обновляем данные с новой структурой (x, y) - СМЕЩАЕМ ИНДЕКСЫ на +1
    currentChart.data.datasets[1].data = xValues.map((x, i) => ({ 
        x: x, 
        y: newData.total_points[i] 
    }));
    
    currentChart.data.datasets[2].data = xValues.map((x, i) => ({ 
        x: x, 
        y: newData.total_values[i] 
    }));
    
    currentChart.data.datasets[3].data = xValues.map((x, i) => ({ 
        x: x, 
        y: newData.pace_data[i] 
    }));
    
    // Обновляем линии макс/мин тоталов - СМЕЩАЕМ ИНДЕКСЫ на +1
    if (maxTotal && currentChart.data.datasets[4]) {
        currentChart.data.datasets[4].data = xValues.map(x => ({ 
            x: x, 
            y: maxTotal 
        }));
        currentChart.data.datasets[4].label = `Макс. тотал: ${maxTotal}`;
    }
    
    if (minTotal && currentChart.data.datasets[5]) {
        currentChart.data.datasets[5].data = xValues.map(x => ({ 
            x: x, 
            y: minTotal 
        }));
        currentChart.data.datasets[5].label = `Мин. тотал: ${minTotal}`;
    }
    
    // Обновляем аннотации для ставки (если есть)
    if (newData.bet_timestamp && currentChart.options.plugins.annotation) {
        const betMinutes = timeToMinutes(newData.bet_timestamp);
        const betIndex = xValues.findIndex(x => x === betMinutes);
        
        if (betIndex !== -1) {
            currentChart.options.plugins.annotation.annotations.betLine.xMin = betMinutes;
            currentChart.options.plugins.annotation.annotations.betLine.xMax = betMinutes;
            currentChart.options.plugins.annotation.annotations.betPoint.xValue = betMinutes;
        }
    }
    
    updateDatasetLabels(currentChart);
    currentChart.update('active');
    updateChartTitleFromData(newData);
}

function updateChartTitleFromData(chartData) {
    if (!chartData.timestamps || chartData.timestamps.length === 0) return;
    
    const lastIndex = chartData.timestamps.length - 1;
    const currentValues = {
        totalPoints: chartData.total_points[lastIndex] || '-',
        totalValue: chartData.total_values[lastIndex] || '-',
        pace: chartData.pace_data[lastIndex] || '-',
        timestamp: chartData.timestamps[lastIndex] || '-',
        score: chartData.scores ? chartData.scores[lastIndex] : '-'
    };
    
    const totalValues = chartData.total_values.filter(val => val !== null && val !== undefined);
    const maxTotal = totalValues.length > 0 ? Math.max(...totalValues) : null;
    
    const initialTotal = chartData.initial_total || (chartData.total_values && chartData.total_values[0]);
    const currentTotal = chartData.total_values && chartData.total_values[lastIndex];
    
    let totalDiffHtml = '';
    if (initialTotal && currentTotal) {
        const totalDiff = (currentTotal - initialTotal).toFixed(1);
        const totalDiffPercent = ((currentTotal - initialTotal) / initialTotal * 100).toFixed(1);
        totalDiffHtml = `💹 Δ Тотала: <strong>${totalDiff > 0 ? '+' : ''}${totalDiff} (${totalDiffPercent > 0 ? '+' : ''}${totalDiffPercent}%)</strong>`;
    }
    
    let maxTotalHtml = '';
    if (maxTotal) {
        maxTotalHtml = `📈 Макс. тотал: <strong>${maxTotal.toFixed(1)}</strong>`;
    }
    
    const chartTitle = document.getElementById('chartTitle');
    if (chartTitle && currentOpenMatchId) {
        const matchInfo = getMatchInfoByMatchId(currentOpenMatchId);
        chartTitle.innerHTML = `
            <div style="text-align: center; padding: 5px 0;">
                <div style="font-size: 20px; font-weight: bold; color: #2c3e50; margin-bottom: 3px;">
                    ${matchInfo.teams}
                </div>
                <div style="font-size: 14px; color: #5d6d7e; margin-bottom: 4px;">
                    ${matchInfo.tournament} 
                </div>
                <div style="font-size: 16px; color: #7f8c8d; background: #f8f9fa; padding: 6px 12px; border-radius: 12px; margin-bottom: 3px;">
                    ⏱️ ${currentValues.timestamp} | 📊 ${currentValues.score}
                </div>
                <div style="font-size: 16px; color: #2c3e50; background: #e8f4fd; padding: 4px 10px; border-radius: 8px; margin-top: 2px;">
                    🏀 Очки: <strong>${currentValues.totalPoints}</strong> | 
                    📈 Тотал: <strong>${currentValues.totalValue}</strong> |
                    ⚡ Темп: <strong>${currentValues.pace}</strong> |
                    ${totalDiffHtml} |
                    ${maxTotalHtml}
                </div>
            </div>
        `;
    }
}

function showMatchChart(matchId, teams) {
    currentOpenMatchId = matchId;
    const matchInfo = getMatchInfoByMatchId(matchId);
    
    fetch(`/api/matches/${matchId}/chart`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                return;
            }
            
            document.getElementById('chartTitle').innerHTML = `
                <div style="text-align: center; padding: 5px 0;">
                    <div style="font-size: 20px; font-weight: bold; color: #2c3e50; margin-bottom: 3px;">
                        ${teams}
                    </div>
                    <div style="font-size: 15px; color: #5d6d7e; margin-bottom: 4px;">
                        ${matchInfo.tournament}
                    </div>
                    <div style="font-size: 14px; color: #7f8c8d; background: #f8f9fa; padding: 4px 12px; border-radius: 12px; display: inline-block;">
                        ⏱️ Текущее время: <strong>${matchInfo.currentTime}</strong>
                    </div>
                </div>
            `;
            
            createChart(data, teams, matchInfo.tournament, matchInfo.currentTime);
            modal.style.display = 'block';
        })
        .catch(error => {
            console.error('Ошибка загрузки графика:', error);
            alert('Ошибка загрузки графика');
        });
}

function createChart(chartData, teams, tournament, currentTime) {
    const ctx = document.getElementById('matchChart').getContext('2d');
    if (currentChart) currentChart.destroy();
    // Конвертируем временные метки в минуты для оси X
    const xValues = chartData.timestamps.map(timeToMinutes);
    window.currentChartData = chartData;
    // Ищем индекс времени ставки в массиве временных меток
    let betTimestampIndex = -1;
    if (chartData.bet_timestamp) {
        const betMinutes = timeToMinutes(chartData.bet_timestamp);       
        // Ищем в массиве timestamps время, которое соответствует ставке
        betTimestampIndex = chartData.timestamps.findIndex(
            time => time === chartData.bet_timestamp
        );
    }    
    const totalValues = chartData.total_values.filter(val => val !== null && val !== undefined);
    const maxTotal = totalValues.length > 0 ? Math.max(...totalValues) : null;
    const minTotal = totalValues.length > 0 ? Math.min(...totalValues) : null;
    updateChartTitleForAnalytics(chartData, teams, tournament, currentTime);
    const annotations = {};
    const periodAnnotations = {};
    
    if (chartData.period_lines) {
        chartData.period_lines.forEach((minute, index) => {
            // Преобразуем минуты в формат времени
            const timeLabel = `${minute}:00`;
            // Находим индекс этого времени в массиве timestamps
            const periodIndex = chartData.timestamps.findIndex(t => t === timeLabel);
            
            if (periodIndex !== -1) {
                periodAnnotations[`period_${index + 1}`] = {
                    type: 'line',
                    xMin: minute,  // ✅ используем индекс, а не минуты
                    xMax: minute,
                    yMin: 0,
                    yMax: 'max',
                    borderColor: 'rgba(255, 165, 0, 0.6)',
                    borderWidth: 2,
                    borderDash: [5, 3],
                    label: {
                        display: true,
                        content: `П${index + 1}`,
                        position: 'start',
                        backgroundColor: 'rgba(255, 165, 0, 0.8)',
                        color: 'white',
                        font: { size: 11, weight: 'bold' }
                    }
                };
            }
        });
    }
    if (betTimestampIndex !== -1) {
        const betMinutes = timeToMinutes(chartData.bet_timestamp);
        annotations.betLine = {
            type: 'line',
            xMin: betMinutes,
            xMax: betMinutes,
            yMin: 0,
            yMax: 'max',
            borderColor: 'rgb(255, 215, 0)',
            borderWidth: 3,
            borderDash: [5, 3],
            label: {
                display: true,
                content: '🍀 ТМ ' + chartData.total_values[betTimestampIndex].toFixed(1),
                position: 'end',
                backgroundColor: 'rgba(255, 215, 0, 0.8)',
                color: '#000',
                font: {
                    size: 12,
                    weight: 'bold'
                }
            }
        };
        
        // ДОБАВЛЯЕМ ТОЧКУ СТАВКИ
        annotations.betPoint = {
            type: 'point',
            xValue: betMinutes,
            yValue: chartData.total_values[betTimestampIndex],
            backgroundColor: 'rgb(255, 215, 0)',
            borderColor: 'rgb(255, 215, 0)',
            borderWidth: 3,
            radius: 6,
            pointStyle: 'circle'
        };
    }
    previousChartData = null;
    const allAnnotations = { ...periodAnnotations, ...annotations };
    currentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.timestamps,
            datasets: [
                // ТЕПЛОВАЯ КАРТА - первый элемент (отображается под всеми)
                {
                    label: 'Тепловая карта продуктивности',
                    originalLabel: 'Тепловая карта продуктивности',
                    data: createHeatmapData(chartData),
                    type: 'bar',
                    backgroundColor: function(context) {
                        // 🔥 БЕРЕМ ОРИГИНАЛЬНОЕ КОЛИЧЕСТВО ОЧКОВ ИЗ raw.points
                        const originalPoints = context.raw?.points || 0;
                        return getHeatmapColor(originalPoints);
                    },
                    borderColor: function(context) {
                        // 🔥 БЕРЕМ ОРИГИНАЛЬНОЕ КОЛИЧЕСТВО ОЧКОВ ИЗ raw.points
                        const originalPoints = context.raw?.points || 0;
                        const color = getHeatmapColor(originalPoints);
                        return color.replace('0.3', '0.8').replace('0.5', '0.9').replace('0.6', '1').replace('0.7', '1').replace('0.8', '1');
                    },
                    borderWidth: 1,
                    borderRadius: 2,
                    borderSkipped: false,
                    barPercentage: 0.9,
                    categoryPercentage: 0.8,
                    barThickness: 'flex',
                    maxBarThickness: 20,
                    minBarLength: 0,
                    order: 0,
                    xAxisID: 'x',
                    yAxisID: 'y'
                },
                {
                    label: 'Очки',
                    originalLabel: 'Очки',
                    data: xValues.map((x, i) => ({x: x, y: chartData.total_points[i]})),
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    borderWidth: 2,
                    tension: 0.1,
                    fill: false
                },
                {
                    label: 'Линия тотала',
                    originalLabel: 'Линия тотала',
                    data: xValues.map((x, i) => ({x: x, y: chartData.total_values[i]})),
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.1,
                    fill: false
                },
                {
                    label: 'Темп игры',
                    originalLabel: 'Темп игры',
                    data: xValues.map((x, i) => ({x: x, y: chartData.pace_data[i]})),
                    borderColor: 'rgb(153, 102, 255)',
                    backgroundColor: 'rgba(153, 102, 255, 0.1)',
                    borderWidth: 2,
                    tension: 0.1,
                    pointStyle: 'circle',
                    pointRadius: 3,
                    fill: false
                },
                {
                    label: `Макс. тотал: ${maxTotal}`,
                    data: xValues.map(x => ({x: x, y: maxTotal})),
                    borderColor: 'rgba(231, 76, 60, 0.8)',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    pointRadius: 0,
                    pointHoverRadius: 0,
                    pointHitRadius: 0,
                    fill: false
                },
                {
                    label: `Мин. тотал: ${minTotal}`,
                    data: xValues.map(x => ({x: x, y: minTotal})),
                    borderColor: 'rgba(46, 204, 113, 0.8)',
                    backgroundColor: 'rgba(46, 204, 113, 0.1)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    pointRadius: 0,
                    pointHoverRadius: 0,
                    pointHitRadius: 0,
                    fill: false
                },
                {
                    label: '🍀 Ставка',
                    data: chartData.timestamps.map((timestamp, index) => {
                        if (index === betTimestampIndex) {
                            // Создаем вертикальную линию - много точек по Y
                            return Array.from({length: 10}, (_, i) => {
                                const minY = 0;  // Минимальное значение Y
                                const maxY = maxTotal || 200;  // Максимальное значение Y
                                return minY + (maxY - minY) * (i / 9);
                            });
                        }
                        return null;
                    }),
                    borderColor: 'rgb(255, 215, 0)',
                    borderWidth: 3,
                    pointRadius: 0,
                    fill: false,
                    tension: 0
                }   
            ]
        },

        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: {
                    type: 'linear',
                    title: {
                        display: true,
                        text: 'Минуты матча'
                    },
                    max: function() {
                        if (chartData.timestamps && chartData.timestamps.length > 0) {
                            const lastTimestamp = chartData.timestamps[chartData.timestamps.length - 1];
                            if (lastTimestamp && lastTimestamp.includes(':')) {
                                const lastMinute = parseInt(lastTimestamp.split(':')[0]) || 0;
                                return Math.min(lastMinute + 1, chartData.total_match_time || 48);
                            }
                        }
                        return chartData.total_match_time || 48;
                    }(),                    
                    ticks: {
                        stepSize: 1, // Шаг сетки 1 минута
                        callback: function(value) {
                            // Отображаем только целые минуты
                            return Number.isInteger(value) ? value + "'" : '';
                        }
                    },
                    grid: {
                        color: function(context) {
                            // Защита от undefined
                            if (!context || context.tick === undefined || context.tick.value === undefined) {
                                return 'rgba(0,0,0,0.05)';
                            }
                            // Более яркая сетка для целых минут
                            return Number.isInteger(context.tick.value) ? 'rgba(0,0,0,0.1)' : 'rgba(0,0,0,0.05)';
                        }
                    }
                },
                y: { 
                    title: { 
                        display: true, 
                        text: 'Очки / Темп',
                        font: { size: 14 }
                    },
                    grid: { color: 'rgba(0, 0, 0, 0.1)' },
                    ticks: {
                        font: { size: 12 }
                    }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            const index = context[0].dataIndex;
                            const timestamp = window.currentChartData.timestamps[index];
                            const score = window.currentChartData.scores ? window.currentChartData.scores[index] : 'N/A';
                            return `Время: ${timestamp} | Счет: ${score}`;
                        },
                        label: function(context) {
                            const datasetLabel = context.dataset.originalLabel || context.dataset.label || '';
                            const value = context.parsed.y;
                            
                            if (datasetLabel === 'Очки') {
                                return `Очки: ${value}`;
                            } else if (datasetLabel === 'Линия тотала') {
                                return `Тотал: ${value}`;
                            } else if (datasetLabel === 'Темп игры') {
                                return `Темп: ${value}`;
                            } else if (datasetLabel.includes('Макс. тотал')) {
                                return `Макс. тотал: ${value}`;
                            } else if (datasetLabel.includes('Мин. тотал')) {
                                return `Мин. тотал: ${value}`;
                            }
                            return `${datasetLabel}: ${value}`;
                        }
                    }
                },
                annotation: {
                    annotations: allAnnotations
                },                        
                legend: {
                    display: true,
                    position: 'bottom',
                    align: 'center',
                    labels: {
                        generateLabels: updateLegendLabels,
                        font: {
                            size: 14,
                            family: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
                        },
                        padding: 20,
                        boxWidth: 15,
                        usePointStyle: true
                    }
                }
            },
            animation: {
                duration: 0
            }
        }
    });
    
    updateDatasetLabels(currentChart);
    currentChart.update('active');
}

// ФУНКЦИЯ ДЛЯ ОБНОВЛЕНИЯ ЗАГОЛОВКА В АНАЛИТИКЕ
function updateChartTitleForAnalytics(chartData, teams, tournament, currentTime) {
    if (!chartData.timestamps || chartData.timestamps.length === 0) return;
    
    const lastIndex = chartData.timestamps.length - 1;
    const currentValues = {
        totalPoints: chartData.total_points[lastIndex] || '-',
        totalValue: chartData.total_values[lastIndex] || '-',
        pace: chartData.pace_data[lastIndex] || '-',
        timestamp: chartData.timestamps[lastIndex] || '-',
        score: chartData.scores ? chartData.scores[lastIndex] : '-'
    };
    
    const totalValues = chartData.total_values.filter(val => val !== null && val !== undefined);
    const maxTotal = totalValues.length > 0 ? Math.max(...totalValues) : null;
    
    const initialTotal = chartData.initial_total || (chartData.total_values && chartData.total_values[0]);
    const currentTotal = chartData.total_values && chartData.total_values[lastIndex];
    
    let totalDiffHtml = '';
    if (initialTotal && currentTotal) {
        const totalDiff = (currentTotal - initialTotal).toFixed(1);
        const totalDiffPercent = ((currentTotal - initialTotal) / initialTotal * 100).toFixed(1);
        totalDiffHtml = `💹 Δ Тотала: <strong>${totalDiff > 0 ? '+' : ''}${totalDiff} (${totalDiffPercent > 0 ? '+' : ''}${totalDiffPercent}%)</strong>`;
    }
    
    let maxTotalHtml = '';
    if (maxTotal) {
        maxTotalHtml = `📈 Макс. тотал: <strong>${maxTotal.toFixed(1)}</strong>`;
    }
    
    const chartTitle = document.getElementById('chartTitle');
    if (chartTitle) {
        chartTitle.innerHTML = `
            <div style="text-align: center; padding: 5px 0;">
                <div style="font-size: 20px; font-weight: bold; color: #2c3e50; margin-bottom: 3px;">
                    ${teams}
                </div>
                <div style="font-size: 14px; color: #5d6d7e; margin-bottom: 4px;">
                    ${tournament || 'Архивный матч'} 
                </div>
                <div style="font-size: 16px; color: #7f8c8d; background: #f8f9fa; padding: 6px 12px; border-radius: 12px; margin-bottom: 3px;">
                    ⏱️ ${currentValues.timestamp} | 📊 ${currentValues.score}
                </div>
                <div style="font-size: 16px; color: #2c3e50; background: #e8f4fd; padding: 4px 10px; border-radius: 8px; margin-top: 2px;">
                    🏀 Очки: <strong>${currentValues.totalPoints}</strong> | 
                    📈 Тотал: <strong>${currentValues.totalValue}</strong> |
                    ⚡ Темп: <strong>${currentValues.pace}</strong> |
                    ${totalDiffHtml} |
                    ${maxTotalHtml}
                </div>
            </div>
        `;
    }
}

// Обновляем легенду для включения тепловой карты
function updateLegendWithHeatmap(chart) {
    const datasets = chart.data.datasets;
    return datasets.map((dataset, index) => {
        let label = dataset.originalLabel || dataset.label || '';
        
        // Специальная обработка для тепловой карты
        if (label.includes('Тепловая карта')) {
            return {
                text: '🔥 ' + label,
                fillStyle: 'rgba(255, 100, 100, 0.6)',
                strokeStyle: 'rgba(255, 100, 100, 1)',
                lineWidth: 2,
                pointStyle: 'rect',
                hidden: !chart.isDatasetVisible(index),
                index: index
            };
        }
        
        return {
            text: label,
            fillStyle: dataset.borderColor,
            strokeStyle: dataset.borderColor,
            lineWidth: 2,
            pointStyle: dataset.pointStyle,
            hidden: !chart.isDatasetVisible(index),
            index: index
        };
    });
}

// Обновляем тултипы для тепловой карты
function extendTooltipsForHeatmap(context) {
    const tooltipItems = context.tooltip.items || [];
    
    tooltipItems.forEach(item => {
        if (item.dataset.label && item.dataset.label.includes('Тепловая карта')) {
            const points = item.parsed.y;
            item.label = `Минута ${item.parsed.x}: ${points} очков`;
        }
    });
}
