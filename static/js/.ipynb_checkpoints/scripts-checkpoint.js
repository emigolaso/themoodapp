document.getElementById('dataForm').addEventListener('submit', async function(event) {
    event.preventDefault();
    const entry = document.getElementById('entry').value;

    // Send data to the backend for processing
    const response = await fetch('/submit_entry', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ entry: entry })
    });

    const result = await response.json();
    document.getElementById('responseMessage').textContent = result.message;
});