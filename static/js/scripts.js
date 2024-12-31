document.addEventListener('DOMContentLoaded', () => {
    const currentPath = window.location.pathname;

    // Only check for redirection based on the session, not localStorage
    if (currentPath !== '/login_page' && currentPath !== '/signup_page') {
        // Let the backend (Flask) handle session verification, no need for token check here
        const appContent = document.getElementById('appContent');
        if (appContent) {
            appContent.style.display = 'block';
        }

        // Handle logout inside the DOMContentLoaded handler
        const logoutButton = document.getElementById('logoutButton');
        if (logoutButton) {
            logoutButton.addEventListener('click', async function() {
                console.log('Logout button clicked!');  // Debugging
                try {
                    const response = await fetch('/logout', { method: 'GET' });

                    // Check if the response was redirected
                    if (response.redirected) {
                        // Redirect to the login page
                        window.location.href = response.url;
                    }
                } catch (error) {
                    console.error('Error:', error);
                }
            });
        }

        //Capture the user's timezone and send it to the backend
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; // Fallback to UTC
        console.log(`Detected timezone: ${timezone}`); // Debugging: log the timezone

        // Send timezone to the backend
        fetch('/set_timezone', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ timezone: timezone })
        }).then(response => {
            if (response.ok) {
                console.log('Timezone successfully sent to backend');
            } else {
                console.error('Failed to send timezone to backend');
            }
        }).catch(error => {
            console.error('Error sending timezone:', error);
        });
    }
});


// Handle form submission
document.getElementById('dataForm').addEventListener('submit', async function(event) {
    event.preventDefault(); // Prevent the default form submission

    const moodSlider = document.getElementById('mood');
    const mood = moodSlider.value;  // Get the mood from the slider
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
            document.getElementById('description').value = ''; // Clear the text area
            moodSlider.value = 5.0; // Reset slider to 5
            document.getElementById('moodOutput').value = 5.0;  // Reset the displayed number to 5
        }
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('responseMessage').textContent = 'An error occurred';
    } finally {
        // Re-enable the submit button
        submitButton.disabled = false;
    }
});

// Handle signup
document.getElementById('signupForm').addEventListener('submit', async function (event) {
    event.preventDefault();  // Prevent the default form submission

    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    try {
        const response = await fetch('/signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email: email, password: password })
        });

        const result = await response.json();
        document.getElementById('signupResponse').textContent = result.message;

        
    } catch (error) {
        document.getElementById('signupResponse').textContent = 'An error occurred.';
        console.error(error);
    }
});

// Handle login
document.getElementById('loginForm').addEventListener('submit', async function (event) {
    event.preventDefault(); // Prevent the default form submission

    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email: email, password: password })
        });

        // If login fails, display the error message
        if (!response.ok) {
            const result = await response.json();
            document.getElementById('loginResponse').textContent = result.message;
        }
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('loginResponse').textContent = 'An error occurred during login.';
    }
});


// Handle logout
document.getElementById('logoutButton').addEventListener('click', async function() {
    try {
        const response = await fetch('/logout', {method: 'GET'});

    } catch (error) {
        console.error('Error:', error);
    }
});