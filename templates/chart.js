// chart.js - логика графиков и тепловых карт

// ==================== ЛИНИЯ СРЕДНЕЙ ВЫСОТЫ СТОЛБЦОВ ====================

// Функция расчета средней высоты столбцов для текущего тотала
function calculateAverageColumnHeight(heatmapData, currentTotal) {
    if (!heatmapData || heatmapData.length === 0 || !currentTotal) {
        return null;
    }
    
    try {
        // Фильтруем только минуты с данными (исключаем нулевые и будущие минуты)
        const validMinutes = heatmapData.filter(item => 
            item.points !== undefined && item.points !== null && item.points > 0
        );
        
        if (validMinutes.length === 0) {
            return null;
        }
        
        // Суммируем все очки за минуту
        const totalPoints = validMinutes.reduce((sum, item) => {
            return sum + (item.points || 0);
        }, 0);
        
        // Среднее количество очков за минуту
        const averagePointsPerMinute = totalPoints / validMinutes.length;
        
        // Преобразуем в высоту столбца (умножаем на коэффициент масштабирования)
        const averageHeight = averagePointsPerMinute * 10;
        
        // Рассчитываем целевую среднюю высоту на основе текущего тотала
        const targetAveragePointsPerMinute = currentTotal / 40; // Предполагаем 40 минут игры
        const targetAverageHeight = targetAveragePointsPerMinute * 10;
        
        return {
            currentAverage: averageHeight,
            targetAverage: targetAverageHeight,
            currentPointsPerMinute: averagePointsPerMinute,
            targetPointsPerMinute: targetAveragePointsPerMinute,
            validMinutesCount: validMinutes.length
        };
    } catch (error) {
        console.error('Ошибка расчета средней высоты:', error);
        return null;
    }
}

// Функция создания данных для линии средней высоты
function createAverageLineData(chartData, averageData) {
    if (!averageData || !chartData.timestamps || chartData.timestamps.length === 0) {
        return [];
    }
    
    try {
        const xValues = chartData.timestamps.map(timeToMinutes);
        const maxX = Math.max(...xValues);
        
        return [{
            x: 0,
            y: averageData.targetAverage
        }, {
            x: maxX,
            y: averageData.targetAverage
        }];
    } catch (error) {
        console.error('Ошибка создания данных линии:', error);
        return [];
    }
}

// Функция обновления средней линии на существующем графике
function updateAverageLine(chart, chartData) {
    if (!chart || !chartData) return;
    
    // Получаем текущий тотал (последнее значение)
    const lastIndex = chartData.total_values.length - 1;
    const currentTotal = chartData.total_values[lastIndex];
    
    if (!currentTotal) return;
    
    // Рассчитываем данные тепловой карты
    const heatmapData = createHeatmapData(chartData);
    const averageData = calculateAverageColumnHeight(heatmapData, currentTotal);
    
    if (!averageData) return;
    
    const averageLineData = createAverageLineData(chartData, averageData);
    
    // Находим индекс датасета со средней линией (индекс 1)
    const averageLineIndex = 1;
    
    if (chart.data.datasets[averageLineIndex]) {
        // Обновляем существующий датасет
        chart.data.datasets[averageLineIndex].data = averageLineData;
        chart.data.datasets[averageLineIndex].label = `Целевая средняя: ${averageData.targetPointsPerMinute.toFixed(1)} очков/мин`;
        chart.data.datasets[averageLineIndex].originalLabel = `Целевая средняя: ${averageData.targetPointsPerMinute.toFixed(1)} очков/мин`;
    }
    
    // Обновляем аннотацию для средней линии
    updateAverageLineAnnotation(chart, averageData);
}

// Функция обновления аннотации для средней линии
function updateAverageLineAnnotation(chart, averageData) {
    if (!chart.options.plugins.annotation) {
        chart.options.plugins.annotation = { annotations: {} };
    }
    
    chart.options.plugins.annotation.annotations.averageLine = {
        type: 'line',
        yMin: averageData.targetAverage,
        yMax: averageData.targetAverage,
        xMin: 0,
        xMax: 'max',
        borderColor: 'rgba(0, 0, 255, 0.6)',
        borderWidth: 2,
        borderDash: [5, 5],
        label: {
            display: true,
            content: `Цель: ${averageData.targetPointsPerMinute.toFixed(1)}/мин`,
            position: 'end',
            backgroundColor: 'rgba(0, 0, 255, 0.8)',
            color: 'white',
            font: {
                size: 12,
                weight: 'bold'
            }
        }
    };
}

// ==================== ТЕПЛОВАЯ КАРТА ====================

// Функция расчета очков за каждую минуту
function calculatePointsPerMinute(chartData) {
    if (!chartData || !chartData.timestamps || !chartData.total_points) {
        return [];
    }
    
    try {
        const pointsPerMinute = [];
        const minuteData = {};
        
        // Собираем все данные по минутам
        chartData.timestamps.forEach((timestamp, index) => {
            if (!timestamp || timestamp === '-' || !timestamp.includes(':')) return;
            
            const timeParts = timestamp.split(':');
            const minute = parseInt(timeParts[0]) || 0;
            const points = chartData.total_points[index] || 0;
            
            if (!minuteData[minute]) {
                minuteData[minute] = [];
            }
            minuteData[minute].push({
                points: points,
                timestamp: timestamp
            });
        });
        
        // Находим максимальную минуту
        const maxMinute = Math.max(...Object.keys(minuteData).map(Number));
        const maxTime = Math.min(maxMinute + 2, 60);
        
        for (let minute = 0; minute <= maxTime; minute++) {
            if (minuteData[minute] && minuteData[minute].length > 0) {
                // Сортируем данные по времени внутри минуты
                const minuteRecords = minuteData[minute].sort((a, b) => {
                    return timeToMinutes(a.timestamp) - timeToMinutes(b.timestamp);
                });
                
                // Берем первую и последнюю запись в минуте
                const firstRecord = minuteRecords[0];
                const lastRecord = minuteRecords[minuteRecords.length - 1];
                
                // Очки за минуту = разница между началом и концом минуты
                const pointsThisMinute = lastRecord.points - (minute > 0 ? getPointsAtMinuteEnd(minute - 1, minuteData) : 0);
                
                pointsPerMinute.push({
                    minute: minute,
                    points: Math.max(0, pointsThisMinute),
                    timestamp: lastRecord.timestamp
                });
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

// Вспомогательная функция для получения очков в конце минуты
function getPointsAtMinuteEnd(minute, minuteData) {
    if (minuteData[minute] && minuteData[minute].length > 0) {
        const records = minuteData[minute].sort((a, b) => {
            return timeToMinutes(a.timestamp) - timeToMinutes(b.timestamp);
        });
        return records[records.length - 1].points;
    }
    return 0;
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

// Функция создания данных для тепловой карты
function createHeatmapData(chartData) {
    try {
        const pointsPerMinute = calculatePointsPerMinute(chartData);
        const heatmapData = [];
        
        pointsPerMinute.forEach(item => {
            heatmapData.push({
                x: item.minute,
                y: Math.min(item.points * 10, 150),
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

// ==================== ФУНКЦИИ ГРАФИКОВ ====================

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
        
        // Специальная обработка для линии средней высоты
        if (label.includes('Целевая средняя')) {
            return {
                text: '🎯 ' + label,
                fillStyle: 'rgba(0, 0, 255, 0.8)',
                strokeStyle: 'rgba(0, 0, 255, 0.8)',
                lineWidth: 2,
                pointStyle: 'line',
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

function updateDatasetLabels(chart) {
    if (!chart || !chart.data || !chart.data.datasets) return;
    
    chart.data.datasets.forEach((dataset, index) => {
        dataset.label = dataset.originalLabel || dataset.label || '';
    });
}

// Функции для графика
function refreshChart(newData) {
    if (!currentChart || !newData.timestamps) return;
    console.log('🔄 Обновление графика. Новые данные:', {
        timestamps: newData.timestamps?.length,
        scores: newData.scores?.length, 
        lastScore: newData.scores?.[newData.scores.length - 1]
    });    
    window.currentChartData = newData;
    
    // Конвертируем временные метки в минуты для оси X
    const xValues = newData.timestamps.map(timeToMinutes);
    
    const totalValues = newData.total_values.filter(val => val !== null && val !== undefined);
    const maxTotal = totalValues.length > 0 ? Math.max(...totalValues) : null;
    const minTotal = totalValues.length > 0 ? Math.min(...totalValues) : null;
    
    // 🔥 ОБНОВЛЯЕМ ДАННЫЕ ТЕПЛОВОЙ КАРТЫ (индекс 0)
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
    
    // 🔥 ОБНОВЛЯЕМ ЛИНИЮ СРЕДНЕЙ ВЫСОТЫ (индекс 1)
    updateAverageLine(currentChart, newData);
    
    // Обновляем очки (индекс 2)
    currentChart.data.datasets[2].data = xValues.map((x, i) => ({ 
        x: x, 
        y: newData.total_points[i] 
    }));
    
    // Обновляем линию тотала (индекс 3)
    currentChart.data.datasets[3].data = xValues.map((x, i) => ({ 
        x: x, 
        y: newData.total_values[i] 
    }));
    
    // Обновляем темп игры (индекс 4)
    currentChart.data.datasets[4].data = xValues.map((x, i) => ({ 
        x: x, 
        y: newData.pace_data[i] 
    }));
    
    // Обновляем линии макс/мин тоталов (индексы 5 и 6)
    if (maxTotal && currentChart.data.datasets[5]) {
        currentChart.data.datasets[5].data = xValues.map(x => ({ 
            x: x, 
            y: maxTotal 
        }));
        currentChart.data.datasets[5].label = `Макс. тотал: ${maxTotal}`;
    }
    
    if (minTotal && currentChart.data.datasets[6]) {
        currentChart.data.datasets[6].data = xValues.map(x => ({ 
            x: x, 
            y: minTotal 
        }));
        currentChart.data.datasets[6].label = `Мин. тотал: ${minTotal}`;
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
    
    // 🔥 ОБНОВЛЯЕМ ЗАГОЛОВОК С ЧЕТВЕРТЯМИ (ВАЖНО!)
    updateChartTitleFromData(newData);
    console.log('✅ Заголовок с четвертями обновлен');
}

function showMatchChart(matchId, teams) {
    currentOpenMatchId = matchId;
    const matchInfo = getMatchInfoByMatchId(matchId);
    
    console.log('🔍 Информация о матче:', {
        matchId: matchId,
        teams: teams,
        matchInfo: matchInfo
    });
    
    fetch(`/api/matches/${matchId}/chart`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                return;
            }
            
            console.log('📊 Создание графика с данными:', {
                teams: teams,
                tournament: matchInfo.tournament,
                currentTime: matchInfo.currentTime
            });
            
            createChart(data, teams, matchInfo.tournament, matchInfo.currentTime);
            modal.style.display = 'block';
        })
        .catch(error => {
            console.error('Ошибка загрузки графика:', error);
            alert('Ошибка загрузки графика');
        });
}

function createChart(chartData, teams, tournament, currentTime) {
    window.currentMatchInfo = {
        teams: teams,
        tournament: tournament,
        currentTime: currentTime
    };    
    const ctx = document.getElementById('matchChart').getContext('2d');
    if (currentChart) currentChart.destroy();
    // Конвертируем временные метки в минуты для оси X
    const xValues = chartData.timestamps.map(timeToMinutes);
    window.currentChartData = chartData;
    
    // Получаем текущий тотал для расчета средней линии
    const lastIndex = chartData.total_values.length - 1;
    const currentTotal = chartData.total_values[lastIndex];
    const averageData = calculateAverageColumnHeight(createHeatmapData(chartData), currentTotal);
    const averageLineData = createAverageLineData(chartData, averageData);
    
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
                        content: `П${index + 2}`,
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
    
    // Добавляем аннотацию для средней линии
    if (averageData) {
        annotations.averageLine = {
            type: 'line',
            yMin: averageData.targetAverage,
            yMax: averageData.targetAverage,
            xMin: 0,
            xMax: 'max',
            borderColor: 'rgba(0, 0, 255, 0.6)',
            borderWidth: 2,
            borderDash: [5, 5],
            label: {
                display: true,
                content: `Цель: ${averageData.targetPointsPerMinute.toFixed(1)} очков/мин`,
                position: 'end',
                backgroundColor: 'rgba(0, 0, 255, 0.8)',
                color: 'white',
                font: {
                    size: 12,
                    weight: 'bold'
                }
            }
        };
    }
    
    previousChartData = null;
    const allAnnotations = { ...periodAnnotations, ...annotations };
    
    currentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.timestamps,
            datasets: [
                // ТЕПЛОВАЯ КАРТА - первый элемент (отображается под всеми) - индекс 0
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
                // ЛИНИЯ СРЕДНЕЙ ВЫСОТЫ - индекс 1
                {
                    label: averageData ? `Целевая средняя: ${averageData.targetPointsPerMinute.toFixed(1)} очков/мин` : 'Целевая средняя',
                    originalLabel: averageData ? `Целевая средняя: ${averageData.targetPointsPerMinute.toFixed(1)} очков/мин` : 'Целевая средняя',
                    data: averageLineData,
                    borderColor: 'rgba(0, 0, 255, 0.8)',
                    backgroundColor: 'rgba(0, 0, 255, 0.1)',
                    borderWidth: 3,
                    borderDash: [8, 4],
                    pointRadius: 0,
                    pointHoverRadius: 0,
                    pointHitRadius: 0,
                    fill: false,
                    tension: 0,
                    order: 1
                },
                // ОЧКИ - индекс 2
                {
                    label: 'Очки',
                    originalLabel: 'Очки',
                    data: xValues.map((x, i) => ({x: x, y: chartData.total_points[i]})),
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    borderWidth: 2,
                    tension: 0.1,
                    fill: false,
                    order: 2
                },
                // ЛИНИЯ ТОТАЛА - индекс 3
                {
                    label: 'Линия тотала',
                    originalLabel: 'Линия тотала',
                    data: xValues.map((x, i) => ({x: x, y: chartData.total_values[i]})),
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.1,
                    fill: false,
                    order: 3
                },
                // ТЕМП ИГРЫ - индекс 4
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
                    fill: false,
                    order: 4
                },
                // МАКС. ТОТАЛ - индекс 5
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
                    fill: false,
                    order: 5
                },
                // МИН. ТОТАЛ - индекс 6
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
                    fill: false,
                    order: 6
                },
                // СТАВКА - индекс 7
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
                    tension: 0,
                    order: 7
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
                            } else if (datasetLabel.includes('Целевая средняя')) {
                                return `Целевая средняя: ${value}`;
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

// Функция расчета счета по четвертям
function calculateQuarterScores(chartData) {
    if (!chartData.timestamps || !chartData.scores) {
        return { quarters: [], total: '0:0' };
    }
    
    try {
        const quarterEnds = chartData.total_match_time === 48 ? [12, 24, 36, 48] : [10, 20, 30, 40];
        const quarters = [];
        
        // Определяем текущую минуту матча
        const lastTimestamp = chartData.timestamps[chartData.timestamps.length - 1];
        const currentMinute = lastTimestamp && lastTimestamp.includes(':') 
            ? parseInt(lastTimestamp.split(':')[0]) || 0 
            : 0;
        
        console.log('🔄 Расчет четвертей. Текущая минута:', currentMinute);
        
        let previousScore = { team1: 0, team2: 0 };
        
        // Обрабатываем каждую четверть
        for (let i = 0; i < quarterEnds.length; i++) {
            const quarterEnd = quarterEnds[i];
            const isQuarterCompleted = currentMinute >= quarterEnd;
            const isCurrentQuarter = currentMinute > (i > 0 ? quarterEnds[i-1] : 0) && currentMinute <= quarterEnd;
            const isFutureQuarter = currentMinute < (i > 0 ? quarterEnds[i-1] : 0);
            
            let quarterScore = '0:0';
            let foundScore = { team1: 0, team2: 0 };
            
            if (isFutureQuarter) {
                // Будущая четверть - еще не началась
                quarterScore = '-:-';
            } else {
                // Ищем последнюю запись до конца четверти (или текущую для незавершенной)
                const searchEndTime = isQuarterCompleted ? quarterEnd : currentMinute;
                let lastRecord = null;
                
                for (let j = 0; j < chartData.timestamps.length; j++) {
                    const timestamp = chartData.timestamps[j];
                    if (timestamp && timestamp.includes(':')) {
                        const minute = parseInt(timestamp.split(':')[0]) || 0;
                        
                        if (minute <= searchEndTime) {
                            lastRecord = {
                                score: chartData.scores[j] || '0:0',
                                timestamp: timestamp,
                                minute: minute
                            };
                        }
                    }
                }
                
                if (lastRecord) {
                    // Парсим счет
                    const scoreParts = lastRecord.score.split(':');
                    foundScore = {
                        team1: parseInt(scoreParts[0]) || 0,
                        team2: parseInt(scoreParts[1]) || 0
                    };
                    
                    // Вычисляем очки за четверть
                    const quarterPointsTeam1 = foundScore.team1 - previousScore.team1;
                    const quarterPointsTeam2 = foundScore.team2 - previousScore.team2;
                    
                    quarterScore = `${quarterPointsTeam1}:${quarterPointsTeam2}`;
                    previousScore = foundScore;
                    
                    console.log(`📊 Q${i+1}: ${isQuarterCompleted ? 'завершена' : 'в процессе'} ${quarterScore} на ${lastRecord.timestamp}`);
                }
            }
            
            quarters.push({
                quarter: i + 1,
                score: quarterScore,
                time: `${quarterEnd}:00`,
                completed: isQuarterCompleted,
                current: isCurrentQuarter,
                future: isFutureQuarter
            });
        }
        
        // Общий счет (последняя запись)
        const totalScore = chartData.scores && chartData.scores.length > 0 
            ? chartData.scores[chartData.scores.length - 1] 
            : '0:0';
        
        return {
            quarters: quarters,
            total: totalScore,
            currentMinute: currentMinute
        };
        
    } catch (error) {
        console.error('❌ Ошибка расчета четвертей:', error);
        return { quarters: [], total: '0:0' };
    }
}

// Функция создания HTML для таблицы четвертей
// Функция создания HTML для таблицы четвертей (без фона)
function createQuarterScoresHtml(quarterData) {
    if (!quarterData.quarters || quarterData.quarters.length === 0) {
        return '';
    }
    
    const quarterItems = quarterData.quarters.map(q => {
        return `
            <div style="display: inline-block; margin: 0 6px; padding: 6px 10px; 
                background: #f8f9fa; 
                border-radius: 8px; 
                min-width: 55px;
                text-align: center;">
                <div style="font-size: 18px; font-weight: bold; color: #2c3e50;">
                    ${q.score}
                </div>
            </div>
        `;
    }).join('');
    
    return `
        <div style="margin: 8px 0; padding: 0;">
            <div style="display: flex; justify-content: center; align-items: center; gap: 8px; flex-wrap: wrap;">
                ${quarterItems}
                <div style="padding: 8px 16px; background: #e8f4fd; border-radius: 8px; border: 2px solid #b3d9ff;">
                    <div style="font-size: 20px; font-weight: bold; color: #2c3e50;">${quarterData.total}</div>
                </div>
            </div>
        </div>
    `;
}

// Обновляем функцию updateChartTitleFromData чтобы включала четверти
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
    
    // 🔥 СЧЕТ ПО ЧЕТВЕРТЯМ
    const quarterScores = calculateQuarterScores(chartData);
    const quarterScoresHtml = createQuarterScoresHtml(quarterScores);
    
    // 🔥 ДАННЫЕ ДЛЯ СРЕДНЕЙ ВЫСОТЫ
    const heatmapData = createHeatmapData(chartData);
    const averageData = calculateAverageColumnHeight(heatmapData, currentTotal);
    
    let averageHtml = '';
    if (averageData) {
        averageHtml = `🎯 Цель: <strong>${averageData.targetPointsPerMinute.toFixed(1)} очков/мин</strong> | `;
        if (averageData.currentPointsPerMinute) {
            averageHtml += `Факт: <strong>${averageData.currentPointsPerMinute.toFixed(1)} очков/мин</strong> | `;
        }
    }
    
    const chartTitle = document.getElementById('chartTitle');
    if (chartTitle && currentOpenMatchId) {
        const matchInfo = window.currentMatchInfo || {
            teams: 'Команда 1 vs Команда 2',
            tournament: 'Турнир',
            currentTime: '0:00'
        };
        chartTitle.innerHTML = `
            <div style="text-align: center; padding: 5px 0;">
                <!-- 🔥 КОМАНДЫ И ТУРНИР В ОДНОЙ СТРОКЕ -->
                <div style="font-size: 20px; font-weight: bold; color: #2c3e50; margin-bottom: 8px;">
                    ${matchInfo.teams} <span style="font-size: 14px; color: #5d6d7e; font-weight: normal;">(${matchInfo.tournament})</span>
                </div>
                
                <!-- 🔥 ОБЪЕДИНЕННАЯ СТРОКА: ВРЕМЯ + СЧЕТ ПО ЧЕТВЕРТЯМ -->
                <div style="display: flex; justify-content: center; align-items: center; gap: 15px; margin-bottom: 8px;">
                    <div style="font-size: 18px; color: #7f8c8d; background: #f8f9fa; padding: 8px 16px; border-radius: 10px;">
                        ⏱️ <strong>${currentValues.timestamp}</strong>
                    </div>
                    ${quarterScoresHtml}
                </div>
                
                <!-- 🔥 АНАЛИТИКА ТЕКУЩЕГО СОСТОЯНИЯ -->
                <div style="font-size: 18px; color: #2c3e50; background: #f8f9fa; padding: 8px 16px; border-radius: 10px; display: inline-block;">
                    ${averageHtml}
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

// Также обновляем updateChartTitleForAnalytics
function updateChartTitleForAnalytics(chartData, teams, tournament, currentTime) {
    updateChartTitleFromData(chartData); // Просто вызываем ту же функцию
}

// Добавьте эту функцию в начало файла chart.js после глобальных переменных
function getMatchInfoByMatchId(matchId) {
    console.log('🔍 Поиск информации о матче:', matchId);
    
    // В первую очередь используем window.currentMatchInfo, если он соответствует текущему матчу
    if (window.currentMatchInfo && window.currentMatchInfo.matchId === matchId) {
        console.log('✅ Используем window.currentMatchInfo:', window.currentMatchInfo);
        return window.currentMatchInfo;
    }
    
    // Если не совпадает, ищем в DOM
    console.log('🔍 Ищем матч в DOM...');
    
    // Пробуем найти в таблице активных матчей
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
    
    // Пробуем найти в таблице архивных матчей
    for (let row of rows) {
        const onclickAttr = row.getAttribute('onclick');
        if (onclickAttr && onclickAttr.includes(`showArchiveChart(${matchId},`)) {
            const matchTeams = row.querySelector('.match-teams');
            const tournamentElement = row.querySelector('.tournament');
            const timeElement = row.querySelector('td:nth-child(4) strong'); // Время в другом столбце в архиве
            
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
    // Возвращаем значения по умолчанию как запасной вариант
    return {
        matchId: matchId,
        teams: 'Команда 1 vs Команда 2',
        tournament: 'Турнир',
        currentTime: '0:00'
    };
}