// bedrock_server_manager/web/static/js/scripts.js
document.addEventListener('DOMContentLoaded', function() {
    const serverSelect = document.getElementById('server-select');
    const startButton = document.querySelector('.start-button');
    const stopButton = document.querySelector('.stop-button');
    const restartButton = document.querySelector('.restart-button');
    const updateButton = document.querySelector('.update-button');

    // Function to update dropdown style based on selection
    function updateDropdownStyle() {
        if (serverSelect.value) {
            serverSelect.classList.add('selected');
        } else {
            serverSelect.classList.remove('selected');
        }
    }

    // Initial style update (on page load)
    updateDropdownStyle();

    // Update style whenever the selection changes
    serverSelect.addEventListener('change', updateDropdownStyle);

    // Add click event listeners to buttons
    if (startButton) {
        startButton.addEventListener('click', function() {
            const selectedServer = serverSelect.value;
            if (selectedServer) {
                window.location.href = `/server/${selectedServer}/start`;
            } else {
                alert('Please select a server.');
            }
        });
    }

    if (stopButton) {
        stopButton.addEventListener('click', function() {
            const selectedServer = serverSelect.value;
            if (selectedServer) {
                window.location.href = `/server/${selectedServer}/stop`;
            } else {
                alert('Please select a server.');
            }
        });
    }

    if (restartButton) {
        restartButton.addEventListener('click', function() {
            const selectedServer = serverSelect.value;
            if (selectedServer) {
                window.location.href = `/server/${selectedServer}/restart`;
            } else {
                alert('Please select a server.');
            }
        });
    }

    if (updateButton) {
        updateButton.addEventListener('click', function() {
            const selectedServer = serverSelect.value;
            if (selectedServer) {
                window.location.href = `/server/${selectedServer}/update`;
            } else {
                alert('Please select a server.');
            }
        });
    }
});