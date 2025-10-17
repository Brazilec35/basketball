// websocket.js
// WebSocket соединение для live-обновлений
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

// Функция обновления открытого графика
function updateOpenChart(matches) {
    if (!window.currentOpenMatchId || !window.currentChart) return;
    
    const currentMatch = matches.find(match => match.id === window.currentOpenMatchId);
    if (currentMatch) {
        fetch(`/api/matches/${window.currentOpenMatchId}/chart`)
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    refreshChart(data);
                }
            })
            .catch(error => console.error('❌ Error updating chart:', error));
    }
}