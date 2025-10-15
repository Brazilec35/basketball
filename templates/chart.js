<!-- chart.js-->
// Функции для обновления легенды графика
function updateLegendLabels(chart) {
    const datasets = chart.data.datasets;
    return datasets.map((dataset, index) => {
        let label = dataset.originalLabel || dataset.label || '';
        
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
    
    showChangesIndicator(newData);            
    window.currentChartData = newData;
    
    const totalValues = newData.total_values.filter(val => val !== null && val !== undefined);
    const maxTotal = totalValues.length > 0 ? Math.max(...totalValues) : null;
    const minTotal = totalValues.length > 0 ? Math.min(...totalValues) : null;
    
    currentChart.data.labels = newData.timestamps;
    currentChart.data.datasets[0].data = newData.total_points;
    currentChart.data.datasets[1].data = newData.total_values;
    currentChart.data.datasets[2].data = newData.pace_data;
    
    if (maxTotal && currentChart.data.datasets[3]) {
        currentChart.data.datasets[3].data = newData.timestamps.map(() => maxTotal);
        currentChart.data.datasets[3].label = `Макс. тотал: ${maxTotal}`;
    }
    
    if (minTotal && currentChart.data.datasets[4]) {
        currentChart.data.datasets[4].data = newData.timestamps.map(() => minTotal);
        currentChart.data.datasets[4].label = `Мин. тотал: ${minTotal}`;
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
    
    window.currentChartData = chartData;
    // Ищем индекс времени ставки в массиве временных меток
    let betTimestampIndex = -1;
    if (chartData.bet_timestamp) {
        // Ищем в массиве timestamps время, которое соответствует ставке
        betTimestampIndex = chartData.timestamps.findIndex(
            time => time === chartData.bet_timestamp
        );
    }    
    const totalValues = chartData.total_values.filter(val => val !== null && val !== undefined);
    const maxTotal = totalValues.length > 0 ? Math.max(...totalValues) : null;
    const minTotal = totalValues.length > 0 ? Math.min(...totalValues) : null;
    const annotations = {};
    if (betTimestampIndex !== -1) {
        annotations.betLine = {
            type: 'line',
            xMin: betTimestampIndex,
            xMax: betTimestampIndex,
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
    }
    previousChartData = null;
    currentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.timestamps,
            datasets: [
                {
                    label: 'Очки',
                    originalLabel: 'Очки',
                    data: chartData.total_points,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    borderWidth: 2,
                    tension: 0.1,
                    fill: false
                },
                {
                    label: 'Линия тотала',
                    originalLabel: 'Линия тотала',
                    data: chartData.total_values,
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
                    data: chartData.pace_data,
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
                    data: chartData.timestamps.map(() => maxTotal),
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
                    data: chartData.timestamps.map(() => minTotal),
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
                    title: { 
                        display: true, 
                        text: 'Время матча',
                        font: { size: 14 }
                    },
                    grid: { color: 'rgba(0, 0, 0, 0.1)' },
                    ticks: {
                        font: { size: 12 }
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
                    annotations: annotations
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