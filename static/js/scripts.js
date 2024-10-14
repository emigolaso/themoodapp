document.getElementById('dataForm').addEventListener('submit', async function(event) {
    event.preventDefault(); // Prevent the default form submission

    const mood = document.getElementById('mood').value;  // Get the mood from the slider
    const description = document.getElementById('description').value;  // Get the description from textarea
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
            body: JSON.stringify({ mood: mood, description: description, timezone: timezone })
        });

        const result = await response.json();

        // Display the response message
        document.getElementById('responseMessage').textContent = result.message;

        // Clear the textarea and reset slider if submission was successful
        if (result.message === 'Data inserted successfully!') {
            document.getElementById('description').value = '';
            document.getElementById('mood').value = 5.0;  // Reset slider to midpoint
        }
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('responseMessage').textContent = 'An error occurred';
    } finally {
        // Re-enable the submit button
        submitButton.disabled = false;
    }
});