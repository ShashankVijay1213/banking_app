from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change in production

DB_FILE = 'banking.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        pin TEXT NOT NULL,
        balance REAL DEFAULT 0.0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        type TEXT,
        amount REAL,
        target TEXT,
        timestamp TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# ---------------- User Functions ----------------

def get_user(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return user

def check_login(username, password):
    user = get_user(username)
    return user and user[1] == password

def verify_pin(username, pin):
    user = get_user(username)
    return user and user[2] == pin

# ---------------- Routes ----------------

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        pin = request.form.get("pin")

        if not username or not password or not pin:
            return "All fields are required", 400

        if len(pin) != 4 or not pin.isdigit():
            return "PIN must be a 4-digit number", 400

        conn = sqlite3.connect("banking.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, pin, balance) VALUES (?, ?, ?, ?)",
                      (username, password, pin, 0.0))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Username already exists", 400

        conn.close()
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password:
        return "Missing credentials", 400
    # Continue login logic


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))
    user = get_user(session['user'])
    return render_template('dashboard.html', balance=user[3])

@app.route('/deposit', methods=['POST'])
def deposit():
    if 'user' not in session:
        return redirect(url_for('index'))
    amount = float(request.form['amount'])
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount, session['user']))
    c.execute("INSERT INTO transactions (username, type, amount, target, timestamp) VALUES (?, 'deposit', ?, NULL, datetime('now'))",
              (session['user'], amount))
    conn.commit()
    conn.close()
    flash("Deposit successful.", "success")
    return redirect(url_for('dashboard'))

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user' not in session:
        return redirect(url_for('index'))
    amount = float(request.form['amount'])
    pin = request.form['pin']
    user = get_user(session['user'])

    if not verify_pin(session['user'], pin):
        flash("Incorrect PIN.", "danger")
        return redirect(url_for('dashboard'))

    if amount > user[3]:
        flash("Insufficient funds.", "danger")
        return redirect(url_for('dashboard'))

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance - ? WHERE username = ?", (amount, session['user']))
    c.execute("INSERT INTO transactions (username, type, amount, target, timestamp) VALUES (?, 'withdraw', ?, NULL, datetime('now'))",
              (session['user'], amount))
    conn.commit()
    conn.close()
    flash("Withdrawal successful.", "success")
    return redirect(url_for('dashboard'))

@app.route('/transfer', methods=['POST'])
def transfer():
    if 'user' not in session:
        return redirect(url_for('index'))
    target = request.form['target']
    amount = float(request.form['amount'])
    pin = request.form['pin']
    sender = get_user(session['user'])
    receiver = get_user(target)

    if not receiver:
        flash("Target user does not exist.", "danger")
        return redirect(url_for('dashboard'))

    if not verify_pin(session['user'], pin):
        flash("Incorrect PIN.", "danger")
        return redirect(url_for('dashboard'))

    if amount > sender[3]:
        flash("Insufficient funds.", "danger")
        return redirect(url_for('dashboard'))

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance - ? WHERE username = ?", (amount, session['user']))
    c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount, target))
    c.execute("INSERT INTO transactions (username, type, amount, target, timestamp) VALUES (?, 'transfer', ?, ?, datetime('now'))",
              (session['user'], amount, target))
    conn.commit()
    conn.close()
    flash("Transfer successful.", "success")
    return redirect(url_for('dashboard'))

@app.route('/transactions')
def transactions():
    if 'user' not in session:
        return redirect(url_for('index'))
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT type, amount, target, timestamp FROM transactions WHERE username = ? ORDER BY timestamp DESC", (session['user'],))
    history = c.fetchall()
    conn.close()
    return render_template('transactions.html', history=history)

@app.route('/delete', methods=['POST'])
def delete():
    if 'user' not in session:
        return redirect(url_for('index'))
    pin = request.form['pin']
    if not verify_pin(session['user'], pin):
        flash("Incorrect PIN.", "danger")
        return redirect(url_for('dashboard'))

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username = ?", (session['user'],))
    c.execute("DELETE FROM transactions WHERE username = ?", (session['user'],))
    conn.commit()
    conn.close()
    session.pop('user', None)
    flash("Account deleted successfully.", "info")
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("Logged out.", "info")
    return redirect(url_for('index'))

# ---------------- Run App ----------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
