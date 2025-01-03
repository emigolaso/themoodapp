document.addEventListener('DOMContentLoaded', () => {
    const currentPath = window.location.pathname;
    
    // If NOT on /login_page or /signup_page, do the "main app" logic
    if (currentPath !== '/login_page' && currentPath !== '/signup_page') {
        const appContent = document.getElementById('appContent');
        if (appContent) {
            appContent.style.display = 'block';
        }

        // Handle logout
        const logoutButton = document.getElementById('logoutButton');
        if (logoutButton) {
            logoutButton.addEventListener('click', async function() {
                console.log('Logout button clicked!');
                try {
                    const response = await fetch('/logout', { method: 'GET' });
                    if (response.redirected) {
                        window.location.href = response.url;
                    }
                } catch (error) {
                    console.error('Error:', error);
                }
            });
        }

    }
    
    // Handle mood form submission (only if #dataForm is on this page)
    const dataForm = document.getElementById('dataForm');
    if (dataForm) {
        dataForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            const moodSlider = document.getElementById('mood');
            const mood = moodSlider.value;
            const description = document.getElementById('description').value;
            let timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

            // Disable the submit button
            const submitButton = dataForm.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
            }
            
            try {
                const response = await fetch('/submit_entry', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mood, description, timezone })
                });
                const result = await response.json();
                
                document.getElementById('responseMessage').textContent = result.message;
                
                if (result.message === 'Data inserted successfully!') {
                    document.getElementById('description').value = '';
                    moodSlider.value = 5.0;
                    document.getElementById('moodOutput').value = 5.0;
                }
            } catch (error) {
                console.error('Error:', error);
                document.getElementById('responseMessage').textContent = 'An error occurred';
            } finally {
                // Re-enable the submit button
                if (submitButton) {
                    submitButton.disabled = false;
                }
            }
        });
    }

    // Handle signup (only if #signupForm is on this page)
    const signupForm = document.getElementById('signupForm');
    if (signupForm) {
        signupForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            
            try {
                const response = await fetch('/signup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });
                const result = await response.json();
                document.getElementById('signupResponse').textContent = result.message;
            } catch (error) {
                document.getElementById('signupResponse').textContent = 'An error occurred.';
                console.error(error);
            }
        });
    }
    
    // Handle login (only if #loginBtn is on this page)
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
      loginForm.addEventListener('submit', async function(event) {
        event.preventDefault(); // <-- Prevent native form submission
    
        console.log("Login button clicked!");
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    
        try {
          const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, timezone })
          });
    
          if (!response.ok) {
            const result = await response.json();
            document.getElementById('loginResponse').textContent = result.message;
          } else {
            // On success, e.g., redirect the user
            window.location.href = '/';
          }
    
        } catch (error) {
          console.error('Error:', error);
          document.getElementById('loginResponse').textContent = 'An error occurred during login.';
        }
      });
    }

    // Handle logout (only if #logoutButton is on this page — some pages may have it, some may not)
    const logoutButtonGlobal = document.getElementById('logoutButton');
    if (logoutButtonGlobal) {
        logoutButtonGlobal.addEventListener('click', async function() {
            try {
                await fetch('/logout', {method: 'GET'});
                // Possibly redirect or handle after logout
            } catch (error) {
                console.error('Error:', error);
            }
        });
    }
});
