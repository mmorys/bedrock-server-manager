// bedrock_server_manager/web/static/js/scripts.js
document.addEventListener('DOMContentLoaded', function() {
    const serverSelect = document.getElementById('server-select');
    const startButton = document.querySelector('.start-button');
    const stopButton = document.querySelector('.stop-button');
    const restartButton = document.querySelector('.restart-button');
    const commandButton = document.querySelector('.command-button');


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

function confirmDelete(serverName) {
    if (confirm(`Are you sure you want to delete server '${serverName}'? This action is irreversible!`)) {
        // If user confirms, submit a form to the delete route
        var form = document.createElement('form');
        form.method = 'POST';
        form.action = `/server/${serverName}/delete`;
        document.body.appendChild(form);
        form.submit();
    }
}

function promptCommand() {
    const serverSelect = document.getElementById('server-select');
    const selectedServer = serverSelect.value;

    if (!selectedServer) {
        alert('Please select a server first.');
        return; // Stop if no server is selected
    }

    const command = prompt("Enter command to send to " + selectedServer + ":");
    if (command !== null && command.trim() !== "") { // Check if command is not null and not just whitespace
        // Send the command using fetch (POST request)
        fetch(`/server/${selectedServer}/send`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json' // Set content type to JSON
            },
            body: JSON.stringify({ command: command }) // Send command in JSON format
        })
        .then(response => response.json())  // Parse JSON response
        .then(data => {
            if (data.status === 'success') {
                flashMessage('Command sent successfully!', 'success');
            } else {
                flashMessage(`Error: ${data.message}`, 'error');
            }
            window.location.reload();
        })
        .catch(error => {
            console.error('Error:', error);
            flashMessage(`Error sending command: ${error}`, 'error');
            window.location.reload();

        });
    }
}

function flashMessage(message, category) {
    const messageBox = document.createElement('div');
    messageBox.className = `message-box message-${category}`;
    messageBox.textContent = message;

    const container = document.querySelector('.container');
    container.insertBefore(messageBox, container.firstChild);

    setTimeout(() => {
        messageBox.style.transition = 'opacity 1s ease-out';
        messageBox.style.opacity = '0';
        setTimeout(() => {
            messageBox.remove();
        }, 1000);
    }, 3000);
}