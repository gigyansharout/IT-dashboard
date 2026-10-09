# Industrial Portal - Setup Guide

This guide explains how to set up the complete project (Frontend + Python Flask Backend + MySQL Database) on a new computer.

## 1. Prerequisites (What you need to install)
Before running anything, ensure the new computer has the following installed:
1. **Python 3.x**: Download and install from [python.org](https://www.python.org/downloads/). *(Make sure to check "Add Python to PATH" during installation).*
2. **MySQL Server**: You need a running MySQL database. The easiest way is to install [XAMPP](https://www.apachefriends.org/index.html) (which includes MySQL/MariaDB) or the official [MySQL Community Server](https://dev.mysql.com/downloads/installer/).

---

## 2. Database Setup
1. Open your MySQL server (e.g., start the "MySQL" module in the XAMPP Control Panel).
2. By default, this application connects to MySQL using the username `root` with a blank password on `localhost`. 
3. **You do not need to manually create the database or tables!** The backend Python script is programmed to automatically create the database (`study_genie_db`) and the `users` table the first time it runs.

*(Note: If your MySQL server has a specific password, you MUST update the `.env` file first. See Step 3).*

---

## 3. Backend Setup (Python Flask)
1. Open a terminal (Command Prompt or PowerShell) and navigate to this project folder.
2. *(Optional but recommended)* Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```
3. Install the required Python packages by running:
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure the Environment:** Open the `.env` file in a text editor.
   - If your MySQL uses a password, change `MYSQL_PASSWORD="YOUR_PASSWORD"`.
   - Update `MAIL_USERNAME` and `MAIL_PASSWORD` if you want the email/OTP features to work properly.
5. Start the backend server:
   ```bash
   python app.py
   ```
   *You should see output indicating that the database was initialized and the Flask server is running on `http://127.0.0.1:5000`.*

---

## 4. Frontend Setup
The frontend consists of plain HTML, CSS, and JS files. 

1. You can simply double-click **`login.html`** or **`register.html`** to open them directly in your web browser.
2. **Best Practice:** For the most reliable behavior (especially with security restrictions on local files and APIs), it is highly recommended to serve the HTML files using a local web server.
   - If you use **VS Code**, install the "Live Server" extension, right-click `login.html`, and select "Open with Live Server".
   - Alternatively, open a *new* terminal window in the project folder and run: `python -m http.server 8000`. Then open your browser to `http://localhost:8000/login.html`.

---

## 5. Testing the Flow
1. Ensure `python app.py` is running in the background.
2. Open `register.html` and create a new account (select a role, enter email/password).
3. Scan the generated QR Code with an Authenticator App (like Google Authenticator or Authy) on your phone.
4. Go to `login.html`. Enter your credentials and solve the captcha.
5. Enter the 6-digit code from your Authenticator App when prompted.
6. You will be successfully logged in!
