from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_mail import Mail, Message
from db import get_db_connection, init_db
import bcrypt
import os
import random
import string
import datetime
import uuid
import pyotp

app = Flask(__name__)
CORS(app)

# Configuration from .env
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'fallback-secret-key')
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

jwt = JWTManager(app)
mail = Mail(app)

# In-memory captcha store (for simplicity)
# Dictionary: captcha_id -> answer
captchas = {}

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

@app.route('/api/captcha', methods=['GET'])
def get_captcha():
    # Generate 5-character alphanumeric captcha
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    captcha_text = ''.join(random.choices(chars, k=5))
    
    captcha_id = str(uuid.uuid4())
    captchas[captcha_id] = captcha_text
    
    return jsonify({"captcha_id": captcha_id, "captcha_text": captcha_text})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')
    employee_id = data.get('employeeId')
    full_name = data.get('fullName')
    mobile_number = data.get('mobileNumber')
    department = data.get('department')
    designation = data.get('designation')
    
    if not all([email, password, employee_id, full_name, mobile_number, department, designation]):
        return jsonify({"message": "Missing required fields"}), 400
        
    if not role:
        if designation == 'Manager':
            role = 'Manager'
        elif designation == 'Admin':
            role = 'Admin'
        else:
            role = 'Employee'
            
    if role not in ['Admin', 'Manager', 'Employee']:
        return jsonify({"message": "Invalid role"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if email exists
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            return jsonify({"message": "User with this Email already exists"}), 409
            
        # Check if employee ID exists
        cursor.execute("SELECT id FROM users WHERE employee_id=%s", (employee_id,))
        if cursor.fetchone():
            return jsonify({"message": "Employee ID already registered"}), 409
            
        # Hash password
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        # Generate PyOTP TOTP Secret
        totp_secret = pyotp.random_base32()
        
        # Insert user (verified by default)
        cursor.execute(
            "INSERT INTO users (email, password_hash, role, totp_secret, is_verified, employee_id, full_name, mobile_number, department, designation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (email, hashed_password, role, totp_secret, True, employee_id, full_name, mobile_number, department, designation)
        )
        conn.commit()
        
        # Generate provisioning URI for QR Code
        totp_auth_url = pyotp.totp.TOTP(totp_secret).provisioning_uri(name=email, issuer_name="Dashboard Login")
        
        return jsonify({
            "message": "Registration successful. Please scan the QR code.",
            "totp_auth_url": totp_auth_url
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"message": f"Database connection failed: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/verify_otp', methods=['POST'])
def verify_otp():
    data = request.json
    email = data.get('email')
    otp = data.get('otp')
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT totp_secret FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        
        if not user or not user['totp_secret']:
            return jsonify({"message": "User not found or secret missing"}), 400
            
        totp = pyotp.TOTP(user['totp_secret'])
        if not totp.verify(otp):
            return jsonify({"message": "Invalid OTP code"}), 400
            
        # Mark user as verified
        cursor.execute("UPDATE users SET is_verified=TRUE WHERE email=%s", (email,))
        conn.commit()
        
        return jsonify({"message": "Account verified successfully"}), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"message": f"Database connection failed: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')
    captcha_id = data.get('captcha_id')
    captcha_answer = data.get('captcha_answer')
    
    # 1. Verify Captcha
    if not captcha_id or captcha_id not in captchas:
        return jsonify({"message": "Invalid captcha session"}), 400
    if captchas[captcha_id] != captcha_answer:
        return jsonify({"message": "Incorrect captcha answer"}), 401
    
    # Optional: Clear used captcha
    del captchas[captcha_id]
    
    # 2. Verify Credentials
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"message": "Invalid credentials"}), 401
            
        if user['role'] != role:
            return jsonify({"message": "Role mismatch. Select correct role."}), 401
            
        if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            # Optional: Check if email is verified
            if not user.get('is_verified'):
                return jsonify({"message": "Please verify your email first"}), 403
                
            # Directly return JWT Access Token and profile details
            access_token = create_access_token(identity=email, additional_claims={'role': user['role']})
            return jsonify({
                "message": "Login successful",
                "access_token": access_token,
                "user": {
                    "email": email,
                    "role": user['role'],
                    "full_name": user.get('full_name', 'Portal Member'),
                    "employee_id": user.get('employee_id', '-')
                }
            }), 200
        else:
            return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"message": f"Database connection failed: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/verify_login_otp', methods=['POST'])
def verify_login_otp():
    data = request.json
    email = data.get('email')
    otp = data.get('otp')
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        
        if not user or not user['totp_secret']:
            return jsonify({"message": "User not found"}), 404
            
        totp = pyotp.TOTP(user['totp_secret'])
        if not totp.verify(otp):
            return jsonify({"message": "Invalid OTP code"}), 400
            
        
        access_token = create_access_token(identity=email, additional_claims={'role': user['role']})
        return jsonify({
            "message": "Login successful",
            "access_token": access_token,
            "user": {
                "email": email,
                "role": user['role'],
                "full_name": user.get('full_name', 'Portal Member'),
                "employee_id": user.get('employee_id', '-')
            }
        }), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"message": f"Database connection failed: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

def get_current_user_claims():
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity.get('email'), identity.get('role')
    claims = get_jwt()
    return identity, claims.get('role')

# Example RBAC Protected Route
@app.route('/api/dashboard_settings', methods=['GET', 'POST'])
@jwt_required()
def dashboard_settings():
    email, role = get_current_user_claims()
    
    if role == 'Employee' and request.method == 'POST':
        return jsonify({"message": "Employees are only allowed to view settings."}), 403
        
    if request.method == 'POST':
        return jsonify({"message": f"{role} successfully updated dashboard settings."}), 200
        
    return jsonify({"message": f"Dashboard settings data. Accessed as {role}"}), 200

# Fetch user profile endpoint
@app.route('/api/user/profile', methods=['GET'])
@jwt_required()
def get_user_profile():
    email, role = get_current_user_claims()
    
    if not email:
        return jsonify({"message": "Invalid token identity"}), 400
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email, role, employee_id, full_name, mobile_number, department, designation FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"message": "User not found"}), 404
            
        return jsonify({
            "email": user['email'],
            "role": user['role'],
            "employee_id": user.get('employee_id', '-'),
            "full_name": user.get('full_name', 'Portal Member'),
            "mobile_number": user.get('mobile_number', ''),
            "department": user.get('department', ''),
            "designation": user.get('designation', '')
        }), 200
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

def log_activity(user_email, action_type, description):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO activity_logs (user_email, action_type, description) VALUES (%s, %s, %s)",
            (user_email, action_type, description)
        )
        conn.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")
    finally:
        if conn:
            conn.close()

@app.route('/api/employees', methods=['GET'])
@jwt_required()
def get_employees():
    email, role = get_current_user_claims()
    
    if role not in ['Manager', 'Admin']:
        return jsonify({"message": "Access denied"}), 403
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, role, employee_id, full_name, mobile_number, department, designation, attendance_status, created_at FROM users ORDER BY created_at DESC")
        employees = cursor.fetchall()
        return jsonify(employees), 200
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/employees', methods=['POST'])
@jwt_required()
def add_employee():
    creator_email, role = get_current_user_claims()
    
    if role not in ['Manager', 'Admin']:
        return jsonify({"message": "Access denied"}), 403
        
    data = request.json
    email = data.get('email')
    password = data.get('password', 'Nalco@123')
    emp_role = data.get('role', 'Employee')
    employee_id = data.get('employeeId')
    full_name = data.get('fullName')
    mobile_number = data.get('mobileNumber')
    department = data.get('department')
    designation = data.get('designation')
    
    if not all([email, employee_id, full_name, mobile_number, department, designation]):
        return jsonify({"message": "Missing required fields"}), 400
        
    if emp_role not in ['Admin', 'Manager', 'Employee']:
        return jsonify({"message": "Invalid role"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if email exists
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            return jsonify({"message": "User with this Email already exists"}), 409
            
        # Check if employee ID exists
        cursor.execute("SELECT id FROM users WHERE employee_id=%s", (employee_id,))
        if cursor.fetchone():
            return jsonify({"message": "Employee ID already registered"}), 409
            
        # Hash password
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        # Generate PyOTP TOTP Secret
        totp_secret = pyotp.random_base32()
        
        cursor.execute(
            "INSERT INTO users (email, password_hash, role, totp_secret, is_verified, employee_id, full_name, mobile_number, department, designation, attendance_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (email, hashed_password, emp_role, totp_secret, True, employee_id, full_name, mobile_number, department, designation, 'Not Marked')
        )
        conn.commit()
        
        log_activity(creator_email, 'Employee Addition', f"Added employee {full_name} ({employee_id})")
        
        return jsonify({"message": "Employee added successfully"}), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/employees/<email>', methods=['PUT'])
@jwt_required()
def update_employee(email):
    updater_email, role = get_current_user_claims()
    
    if role not in ['Manager', 'Admin']:
        return jsonify({"message": "Access denied"}), 403
        
    data = request.json
    full_name = data.get('fullName')
    mobile_number = data.get('mobileNumber')
    department = data.get('department')
    designation = data.get('designation')
    emp_role = data.get('role')
    attendance_status = data.get('attendanceStatus')
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch old details to log differences
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        old_user = cursor.fetchone()
        if not old_user:
            return jsonify({"message": "Employee not found"}), 404
            
        cursor.execute(
            "UPDATE users SET full_name=%s, mobile_number=%s, department=%s, designation=%s, role=%s, attendance_status=%s WHERE email=%s",
            (full_name, mobile_number, department, designation, emp_role, attendance_status, email)
        )
        conn.commit()
        
        if old_user.get('attendance_status') != attendance_status:
            log_activity(updater_email, 'Attendance Modification', f"Changed attendance status for {full_name} to '{attendance_status}'")
        else:
            log_activity(updater_email, 'Employee Update', f"Updated details for employee {full_name} ({old_user.get('employee_id')})")
            
        return jsonify({"message": "Employee updated successfully"}), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/employees/<email>', methods=['DELETE'])
@jwt_required()
def delete_employee(email):
    deleter_email, role = get_current_user_claims()
    
    if role not in ['Manager', 'Admin']:
        return jsonify({"message": "Access denied"}), 403
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT full_name, employee_id FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"message": "Employee not found"}), 404
            
        cursor.execute("DELETE FROM users WHERE email=%s", (email,))
        conn.commit()
        
        log_activity(deleter_email, 'Employee Removal', f"Removed employee record: {user.get('full_name')} ({user.get('employee_id')})")
        
        return jsonify({"message": "Employee deleted successfully"}), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/user/profile', methods=['PUT'])
@jwt_required()
def update_self_profile():
    email, role = get_current_user_claims()
    
    if not email:
        return jsonify({"message": "Invalid token"}), 400
        
    data = request.json
    full_name = data.get('fullName')
    mobile_number = data.get('mobileNumber')
    department = data.get('department')
    designation = data.get('designation')
    
    if not all([full_name, mobile_number, department, designation]):
        return jsonify({"message": "Missing required fields"}), 400
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"message": "User not found"}), 404
            
        cursor.execute(
            "UPDATE users SET full_name=%s, mobile_number=%s, department=%s, designation=%s WHERE email=%s",
            (full_name, mobile_number, department, designation, email)
        )
        conn.commit()
        
        log_activity(email, 'Profile Change', f"User updated their own profile details")
        
        return jsonify({"message": "Profile updated successfully"}), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/activity_logs', methods=['GET'])
@jwt_required()
def get_activity_logs():
    email, role = get_current_user_claims()
    
    if role not in ['Manager', 'Admin']:
        return jsonify({"message": "Access denied"}), 403
        
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_email, action_type, description, timestamp FROM activity_logs ORDER BY timestamp DESC")
        logs = cursor.fetchall()
        return jsonify(logs), 200
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/support/chat', methods=['POST'])
def support_chat():
    data = request.json or {}
    message = (data.get('message') or '').strip().lower()
    
    if not message:
        return jsonify({"reply": "I am the Dashboard Support Assistant. How can I help you today?"}), 400
        
    # Check if the query is unrelated to the system (out of scope check)
    dashboard_keywords = [
        'login', 'sign in', 'register', 'sign up', 'account', 'credential', 'captcha',
        'password', 'forgot', 'reset', 'role', 'admin', 'manager', 'employee',
        'dashboard', 'kpi', 'chart', 'asset', 'table', 'registry', 'theme', 'export', 'pdf', 'png',
        'profile', 'edit', 'update', 'setting', 'permission', 'privilege',
        'attendance', 'present', 'absent', 'leave', 'vacation', 'log', 'activity', 'audit',
        'report', 'support', 'help', 'contact', 'troubleshoot', 'error', 'navigation',
        'navigate', 'click', 'notification', 'alert', 'feature'
    ]
    
    if not any(k in message for k in dashboard_keywords):
        return jsonify({
            "reply": "I am an AI Assistant specialized only in the NALCO Employee Management Dashboard. "
                     "I cannot answer queries unrelated to this system. Please ask dashboard-related questions "
                     "(e.g., login, profile edits, employee records, attendance, admin settings, etc.)."
        }), 200

    # 1. Login and Account Access / Captcha
    if any(k in message for k in ['login', 'sign in', 'access', 'credentials']):
        response_text = (
            "To log in to the system step-by-step:<br>"
            "1. Navigate to the login page at [http://localhost:8000/login.html](http://localhost:8000/login.html).<br>"
            "2. Select your correct role (**Admin**, **Manager**, or **Employee**) using the role toggle selector at the top of the form.<br>"
            "3. Enter your registered email address and password in the respective input fields.<br>"
            "4. View the 5-character captcha code and type it exactly into the captcha answer field.<br>"
            "5. Click the blue **Login** button. If the inputs are correct, you will be redirected to the dashboard."
        )

    # 2. Captcha / Captcha Troubleshooting
    elif 'captcha' in message:
        response_text = (
            "To troubleshoot and resolve captcha issues:<br>"
            "1. Click the refresh icon (**🔄**) directly inside the captcha input area to load a new code.<br>"
            "2. Type the alphanumeric code exactly as shown (answers are case-sensitive).<br>"
            "3. If you get a 'Incorrect captcha answer' error, try reloading the page or check if your browser blocks cookies or session storage."
        )

    # 3. Registration / Create Account / 2FA
    elif any(k in message for k in ['register', 'sign up', 'create account', 'new account']):
        response_text = (
            "To register a new dashboard account step-by-step:<br>"
            "1. Open the registration page at [http://localhost:8000/register.html](http://localhost:8000/register.html).<br>"
            "2. Fill in all required information: Employee ID, Full Name, Email, Mobile Number, Department, and Designation.<br>"
            "3. Enter a secure password and re-enter it in the confirm password field.<br>"
            "4. View the captcha code, type it, check the 'Agree to Terms and Conditions' checkbox, and click **Register**.<br>"
            "5. On the Two-Factor Authentication (2FA) screen, scan the QR code using Google Authenticator or Authy, enter the 6-digit verification code, and click **Verify & Activate** to finalize your account setup."
        )

    # 4. Navigation & Layout Guide
    elif any(k in message for k in ['navigation', 'navigate', 'click', 'layout', 'where to find']):
        response_text = (
            "Here is the navigation and layout guide for the dashboard:<br>"
            "1. **Identity & Profile (Top-Left)**: Click on your user identity card (displays your name/Employee ID) to edit your self-profile.<br>"
            "2. **Theme Swatches (Top-Right)**: Admins can click on color circles (Blue, Green, Amber) to dynamically switch themes.<br>"
            "3. **Export Reports (Top-Right)**: Admins can click the **Export PNG** or **Export PDF** buttons.<br>"
            "4. **Sidebar Navigation (Left)**:<br>"
            "   * **Dashboard**: Overview charts and KPI blocks (visible to all roles).<br>"
            "   * **Employees**: Employee registry table and CRUD options (Managers & Admins only; hidden from Employees).<br>"
            "   * **Activity Log**: Chronological audit logs (Managers & Admins only; hidden from Employees)."
        )

    # 5. Editing Profiles (Self-Profile)
    elif any(k in message for k in ['profile', 'edit profile', 'update profile', 'change profile', 'my profile']):
        response_text = (
            "All users (Admins, Managers, and Employees) can update their profile details step-by-step:<br>"
            "1. Click on the **User Identity card** in the top-left corner of the header bar.<br>"
            "2. The **My Profile Settings** pop-up modal will display your current details.<br>"
            "3. Modify your Full Name, Mobile Number, Department, or Designation in the input fields.<br>"
            "4. Click the **Update Profile** button. The system will save changes immediately and update the header display."
        )

    # 6. Managing Employees
    elif any(k in message for k in ['manage employee', 'edit employee', 'delete employee', 'add employee', 'remove employee', 'records']):
        response_text = (
            "**Permissions Restriction**: Standard Employees do not have permission to manage or view employee records. "
            "If changes are needed, please contact your Manager or Administrator.<br><br>"
            "For **Managers** and **Admins**, you can manage employee records step-by-step:<br>"
            "1. Click the **Employees** tab in the left sidebar.<br>"
            "2. **Add**: Click **+ Add Employee** at the top-right of the table, fill in details, and click **Save**.<br>"
            "3. **Edit**: Click the **Edit** button in the employee's row, modify details in the modal, and click **Save**.<br>"
            "4. **Delete**: Click the red **Delete** button in the row and confirm. (Note: You cannot delete your own logged-in account)."
        )

    # 7. Attendance Status
    elif any(k in message for k in ['attendance', 'present', 'absent']):
        response_text = (
            "**Permissions Restriction**: Standard Employees cannot modify attendance status. "
            "Please notify your Manager if your attendance needs to be updated.<br><br>"
            "For **Managers** and **Admins**, you can modify attendance status step-by-step:<br>"
            "1. Go to the **Employees** tab in the left sidebar.<br>"
            "2. Find the target employee row and locate the **Actions** column on the right.<br>"
            "3. Click the yellow **Attendance** button.<br>"
            "4. Choose **Present**, **Absent**, or **On Leave** from the status dropdown menu.<br>"
            "5. Click **Save** to update their status. This will generate an entry in the system Activity Log."
        )

    # 8. Leave Requests
    elif any(k in message for k in ['leave request', 'request leave', 'apply leave', 'leave']):
        response_text = (
            "**Information Status**: Leave request management is currently unavailable in the system. "
            "We do not have leave request forms or leave records in the current version of the dashboard. "
            "Please contact HR or your manager directly to apply for leaves."
        )

    # 9. Activity Logs
    elif any(k in message for k in ['activity log', 'logs', 'audit', 'feed', 'history']):
        response_text = (
            "**Permissions Restriction**: Standard Employees do not have permission to view activity logs.<br><br>"
            "For **Managers** and **Admins**, you can review system logs step-by-step:<br>"
            "1. Click the **Activity Log** tab in the left sidebar.<br>"
            "2. Inspect the feed displaying Timestamp, Performer Email, Action Type (e.g. Employee Addition, Profile Change), and Description.<br>"
            "3. Use the search bar at the top-right of the log view to search for specific users or action types."
        )

    # 10. Reports & Exports
    elif any(k in message for k in ['report', 'export', 'pdf', 'png']):
        response_text = (
            "**Permissions Restriction**: Managers and Employees do not have access to report exports. "
            "Please contact an Admin to download dashboard reports.<br><br>"
            "For **Admins**, you can export dashboard metrics step-by-step:<br>"
            "1. Locate the **Export PNG** or **Export PDF** buttons in the top-right header bar.<br>"
            "2. Click the button corresponding to your desired format.<br>"
            "3. The system will convert dashboard visual states and download the document directly to your device."
        )

    # 11. Notifications
    elif any(k in message for k in ['notification', 'alert']):
        response_text = (
            "**Information Status**: The dashboard does not have a persistent notification center or notification panel. "
            "Notifications are shown as transient pop-up alerts in the top-right corner of the screen when actions are completed "
            "(e.g., successful login, profile update, or employee record modification)."
        )

    # 12. Password Resets
    elif any(k in message for k in ['password', 'reset', 'forgot']):
        response_text = (
            "Self-service password resets are currently unavailable in this portal. "
            "Please contact your IT Administrator or local Manager to reset your password or verify account credentials."
        )

    # 13. Settings & Permissions
    elif any(k in message for k in ['setting', 'permission', 'privilege', 'feature']):
        response_text = (
            "**Permissions Restriction**: Only Admins have access to edit dashboard settings (custom KPI cards, theme customization, and exporting reports). "
            "Managers have access to view dashboard metrics, view logs, and perform full CRUD operations on employee records. "
            "Employees have read-only access to dashboard metrics and can only edit their own self-profile settings.<br><br>"
            "For **Admins**, you can manage permissions and settings step-by-step:<br>"
            "* **Theme Settings**: Click theme swatches (Blue, Green, Amber) in the top-right header to switch theme colors.<br>"
            "* **KPI Cards**: Click **+ Add KPI** in the KPI cards area, or use the trash icon inside any card to remove it.<br>"
            "* **Text Edit**: Admins and Managers can edit KPI names and chart titles inline by clicking the pencil icon next to editable headers."
        )

    # 14. General Troubleshooting
    elif any(k in message for k in ['troubleshoot', 'error', 'support', 'help', 'contact']):
        response_text = (
            "Here is troubleshooting assistance for common dashboard issues:<br>"
            "1. **Incorrect Captcha**: Click the refresh icon (**🔄**) inside the captcha input block and retype the code accurately (case-sensitive).<br>"
            "2. **Login Fails**: Ensure you selected the correct role toggle (**Admin**, **Manager**, or **Employee**) that matches your account.<br>"
            "3. **Missing Tabs**: If you do not see 'Employees' or 'Activity Log' in the sidebar, verify your role. Standard Employees do not have permission to view these tabs.<br>"
            "4. **API Connection Error**: Verify that the backend Flask server is running at port 5000."
        )

    # 15. General Support / Fallback HELP menu
    else:
        response_text = (
            "I am the NALCO Dashboard AI Assistant. How can I help you? Choose one of the topics below:<br>"
            "* **Login/Access**: Step-by-step logging in or resolving captchas.<br>"
            "* **Profile Edits**: How to update your own profile details.<br>"
            "* **Employee CRUD**: Step-by-step manager guidance on managing employees.<br>"
            "* **Attendance**: Marking attendance status (Present, Absent, On Leave).<br>"
            "* **Activity Logs**: Auditing system operations.<br>"
            "* **Admin Settings**: Managing themes, KPI cards, and exporting reports.<br>"
            "* **Troubleshooting**: Solutions for login errors and captchas."
        )
        
    return jsonify({"reply": response_text}), 200

if __name__ == '__main__':
    # Attempt to initialize DB schema on start
    try:
        init_db()
    except Exception as e:
        print(f"Warning: DB init failed. Start your MySQL server. Error: {e}")
        
    app.run(debug=True, port=5000)
