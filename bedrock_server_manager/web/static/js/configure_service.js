// bedrock_server_manager/web/static/js/create_service.js
        function enableLingering() {
            fetch('/api/enable_lingering')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                  document.getElementById('lingering-message').innerHTML = '<p>Lingering enabled successfully.</p>';
                }
                else {
                  document.getElementById('lingering-message').innerHTML = `<p>Error enabling lingering: ${data.message}</p>`;
                }
            })
             .catch(error => {
                console.error('Error:', error);
                document.getElementById('lingering-message').innerHTML = '<p>Error enabling lingering.</p>';
            });
        }
        document.addEventListener("DOMContentLoaded",() => {
          {% if os == 'Linux' %}
            fetch('/api/lingering_status')
              .then(response => response.json())
              .then(data => {
                const lingeringMessage = document.getElementById('lingering-message');
                if (data.status === 'success'){
                  if (!data.enabled){
                    lingeringMessage.innerHTML = `<p>Lingering is not enabled for your user. \
                    This is required for servers to start automatically on boot and after logout.  \
                    <button onclick="enableLingering()">Enable Lingering</button></p>`;
                  } else {
                    lingeringMessage.innerHTML = "<p>Lingering is enabled.</p>";
                  }
                }
                else {
                  lingeringMessage.innerHTML = `<p>Error: ${data.message}</p>`;
                }

              });
          {% endif %}
        });