// bedrock_server_manager/web/static/js/monitor_usage.js
function updateStatus() {
    fetch(`/api/server/${serverName}/status`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                const info = data.process_info;
                document.getElementById('status-info').textContent = `
PID:          ${info.pid}
CPU Usage:    ${info.cpu_percent.toFixed(1)}%
Memory Usage: ${info.memory_mb.toFixed(1)} MB
Uptime:       ${info.uptime}
                        `.trim();
            } else {
                document.getElementById('status-info').textContent = `Error: ${data.message}`;
            }
        })
        .catch(error => {
            console.error('Error fetching server status:', error);
            document.getElementById('status-info').textContent = `Error fetching server status: ${error}`;
        });
}

document.addEventListener('DOMContentLoaded', function() {
    updateStatus();
    setInterval(updateStatus, 2000);
});