document.addEventListener('DOMContentLoaded', () => {
    // Identify which page we are on
    const isLogin = document.getElementById('loginForm') !== null;
    const isRegister = document.getElementById('registerForm') !== null;
    
    // Elements
    const togglePasswordBtn = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('password');
    const otpForm = document.getElementById('otpForm');
    
    let flowType = ''; // 'login' or 'register'
    let flowEmail = '';
    
    // Toggle Password Visibility
    if (togglePasswordBtn && passwordInput) {
        togglePasswordBtn.addEventListener('click', () => {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            
            // Toggle Icon
            const icon = togglePasswordBtn.querySelector('i');
            if (type === 'text') {
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            } else {
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        });
    }

    // Captcha Logic (Only on Login Page)
    if (isLogin) {
        const captchaBox = document.getElementById('captcha');
        const captchaIdInput = document.getElementById('captchaId');
        const refreshCaptchaBtn = document.getElementById('refreshCaptcha');
        
        const loadCaptcha = async () => {
            try {
                const res = await fetch('http://127.0.0.1:5000/api/captcha');
                const data = await res.json();
                if (captchaBox) captchaBox.innerText = data.captcha_text;
                if (captchaIdInput) captchaIdInput.value = data.captcha_id;
            } catch (error) {
                console.error("Failed to load captcha", error);
                if (captchaBox) captchaBox.innerText = "ERROR";
            }
        };

        if (refreshCaptchaBtn) {
            refreshCaptchaBtn.addEventListener('click', loadCaptcha);
        }
        
        // Load initial captcha
        loadCaptcha();

        // Login Submit
        const loginForm = document.getElementById('loginForm');
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const email = document.getElementById('email').value.trim();
            const password = passwordInput.value;
            const role = document.querySelector('input[name="role"]:checked').value;
            const captchaAnswer = document.getElementById('captchaAnswer').value.trim();
            const captchaId = document.getElementById('captchaId').value;
            
            if (!email || !password || !captchaAnswer) {
                showMessage(loginForm, 'Please fill in all fields.', 'error');
                return;
            }

            const submitBtn = document.getElementById('loginBtn');
            submitBtn.classList.add('loading');
            clearMessage(loginForm);

            try {
                const response = await fetch('http://127.0.0.1:5000/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password, role, captcha_id: captchaId, captcha_answer: captchaAnswer })
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    // Reload captcha on failed login
                    loadCaptcha();
                    document.getElementById('captchaAnswer').value = '';
                    throw new Error(data.message || 'Login failed');
                }
                
                // Success
                localStorage.setItem('study_genie_token', data.access_token);
                localStorage.setItem('study_genie_role', data.user.role);
                localStorage.setItem('employeeName', data.user.full_name || 'Portal Member');
                localStorage.setItem('employeeId', data.user.employee_id || '-');
                localStorage.setItem('flowEmail', email);
                showMessage(loginForm, 'Login successful!', 'success');
                setTimeout(() => {
                    window.location.href = 'dashboard.html';
                }, 2000);
                
            } catch (error) {
                showMessage(loginForm, error.message, 'error');
            } finally {
                submitBtn.classList.remove('loading');
            }
        });
    }

    // Register & OTP Logic
    if (isRegister) {
        const registerForm = document.getElementById('registerForm');
        const captchaBox = document.getElementById('captcha');
        const refreshCaptchaBtn = document.getElementById('refreshCaptcha');
        
        let generatedCaptcha = '';
        
        const generateCaptcha = () => {
            const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
            let captcha = "";
            for (let i = 0; i < 5; i++) {
                captcha += chars.charAt(Math.floor(Math.random() * chars.length));
            }
            generatedCaptcha = captcha;
            if (captchaBox) {
                captchaBox.innerText = captcha;
            }
        };
        
        if (refreshCaptchaBtn) {
            refreshCaptchaBtn.addEventListener('click', generateCaptcha);
        }
        
        // Generate initial captcha
        generateCaptcha();

        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const employeeId = document.getElementById('empid').value.trim();
            const fullName = document.getElementById('fullname').value.trim();
            const email = document.getElementById('email').value.trim();
            const mobileNumber = document.getElementById('mobile').value.trim();
            const department = document.getElementById('department').value;
            const designation = document.getElementById('designation').value;
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            const captchaInput = document.getElementById('captchaInput').value.trim();
            const termsChecked = document.getElementById('terms').checked;
            
            // Front-end validations
            if (mobileNumber.length !== 10) {
                showMessage(registerForm, 'Mobile Number must be exactly 10 digits.', 'error');
                return;
            }
            
            if (password !== confirmPassword) {
                showMessage(registerForm, 'Passwords do not match.', 'error');
                return;
            }
            
            if (captchaInput !== generatedCaptcha) {
                showMessage(registerForm, 'Incorrect Captcha. Please try again.', 'error');
                generateCaptcha();
                document.getElementById('captchaInput').value = '';
                return;
            }
            
            if (!termsChecked) {
                showMessage(registerForm, 'You must agree to the Terms & Conditions.', 'error');
                return;
            }

            const submitBtn = document.getElementById('registerBtn');
            submitBtn.classList.add('loading');
            clearMessage(registerForm);

            try {
                const response = await fetch('http://127.0.0.1:5000/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        employeeId,
                        fullName,
                        email,
                        mobileNumber,
                        department,
                        designation,
                        password
                    })
                });
                
                const data = await response.json();
                
                if (!response.ok) throw new Error(data.message || 'Registration failed');
                
                // Save name for dashboard
                localStorage.setItem("employeeName", fullName);

                showMessage(registerForm, 'Registration successful! Redirecting to login...', 'success');
                setTimeout(() => {
                    window.location.href = 'login.html';
                }, 2000);
                
            } catch (error) {
                showMessage(registerForm, error.message, 'error');
            } finally {
                submitBtn.classList.remove('loading');
            }
        });
    }

    // Verify OTP Submit (Handles both Login and Registration)
    if (otpForm) {
        otpForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const otp = document.getElementById('otp').value.trim();
            
            if (!otp) return;

            const submitBtn = document.getElementById('verifyOtpBtn');
            submitBtn.classList.add('loading');
            clearMessage(otpForm);
            
            const endpoint = flowType === 'login' ? 'http://127.0.0.1:5000/api/verify_login_otp' : 'http://127.0.0.1:5000/api/verify_otp';

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: flowEmail, otp })
                });
                
                const data = await response.json();
                
                if (!response.ok) throw new Error(data.message || 'OTP Verification failed');
                
                if (flowType === 'login') {
                    localStorage.setItem('study_genie_token', data.access_token);
                    localStorage.setItem('study_genie_role', data.user.role);
                    localStorage.setItem('employeeName', data.user.full_name || 'Portal Member');
                    localStorage.setItem('employeeId', data.user.employee_id || '-');
                    localStorage.setItem('flowEmail', flowEmail);
                    showMessage(otpForm, 'Login successful! Redirecting to Dashboard...', 'success');
                    setTimeout(() => {
                        window.location.href = 'dashboard.html';
                    }, 2000);
                } else {
                    showMessage(otpForm, 'Account verified! Redirecting to login...', 'success');
                    setTimeout(() => {
                        window.location.href = 'login.html';
                    }, 2000);
                }
                
            } catch (error) {
                showMessage(otpForm, error.message, 'error');
            } finally {
                submitBtn.classList.remove('loading');
            }
        });
    }

    // UI Helpers
    function showMessage(form, text, type) {
        let msgContainer = form.querySelector('.message-container');
        
        if (!msgContainer) {
            msgContainer = document.createElement('div');
            msgContainer.className = `message-container ${type}`;
            form.insertBefore(msgContainer, form.firstChild);
        } else {
            msgContainer.className = `message-container ${type}`;
        }
        
        msgContainer.innerHTML = `
            <i class="fa-solid ${type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-check'}"></i>
            <span>${text}</span>
        `;
        msgContainer.style.display = 'flex';
    }
    
    function clearMessage(form) {
        const msgContainer = form.querySelector('.message-container');
        if (msgContainer) {
            msgContainer.style.display = 'none';
        }
    }
});
