document.getElementById('dataForm').addEventListener('submit', async function(event) {
    event.preventDefault(); // Prevent the default form submission

    const entry = document.getElementById('entry').value;
    let timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

    // Fallback to "UTC" if timezone is not captured
    if (!timezone) {
        timezone = "UTC";
    }

    // Disable the submit button to prevent multiple submissions
    const submitButton = document.querySelector('button[type="submit"]');
    submitButton.disabled = true;

    try {
        // Send data to the backend for processing
        const response = await fetch('/submit_entry', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ entry: entry, timezone: timezone })
        });

        const result = await response.json();

        // Display the response message
        document.getElementById('responseMessage').textContent = result.message;

        // Clear the text area if submission was successful
        if (result.message === 'Data inserted successfully!') {
            document.getElementById('entry').value = '';
        }
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('responseMessage').textContent = 'An error occurred';
    } finally {
        // Re-enable the submit button
        submitButton.disabled = false;
    }
});