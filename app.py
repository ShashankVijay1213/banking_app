from flask import Flask, render_template_string, request, redirect, session, flash, send_file
import os, json, hashlib, datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key'

DATA_DIR = 'data'
USER_FILE = os.path.join(DATA_DIR, 'users.json')
TX_FILE = os.path.join(DATA_DIR, 'transactions.json')

# Ensure data folder exists
os.makedirs(DATA_DIR, exist_ok=True)
if not os.path.exists(USER_FILE): json.dump({}, open(USER_FILE, 'w'))
if not os.path.exists(TX_FILE): json.dump([], open(TX_FILE, 'w'))

# --- Utility Functions ---
def load_users():
    with open(USER_FILE) as f: return json.load(f)

def save_users(users):
    with open(USER_FILE, 'w') as f: json.dump(users, f, indent=2)

def load_tx():
    with open(TX_FILE) as f: return json.load(f)

def save_tx(txs):
    with open(TX_FILE, 'w') as f: json.dump(txs, f, indent=2)

def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

def log_tx(user, type_, amount, target=None):
    txs = load_tx()
    txs.append({
        "user": user,
        "type": type_,
        "amount": amount,
        "target": target,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_tx(txs)

# --- Routes ---
@app.route('/')
def home():
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        pin = request.form['pin']
        users = load_users()
        if name in users:
            flash('User already exists.')
        else:
            users[name] = {
                'pin': hash_pin(pin),
                'balance': 0
            }
            save_users(users)
            flash('Registration successful. Please log in.')
            return redirect('/login')
    return render_template_string(register_html)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        pin = request.form['pin']
        users = load_users()
        if name in users and users[name]['pin'] == hash_pin(pin):
            session['user'] = name
            flash('Logged in successfully.')
            return redirect('/dashboard')
        else:
            flash('Invalid credentials.')
    return render_template_string(login_html)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect('/login')
    user = session['user']
    users = load_users()
    balance = users[user]['balance']
    return render_template_string(dashboard_html, user=user, balance=balance)

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out.')
    return redirect('/login')

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user' not in session: return redirect('/login')
    amount = float(request.form['amount'])
    pin = request.form['pin']
    users = load_users()
    user = session['user']
    if users[user]['pin'] != hash_pin(pin):
        flash('Incorrect PIN.')
    elif users[user]['balance'] < amount:
        flash('Insufficient balance.')
    else:
        users[user]['balance'] -= amount
        save_users(users)
        log_tx(user, 'withdraw', amount)
        flash('Withdrawal successful.')
    return redirect('/dashboard')

@app.route('/deposit', methods=['POST'])
def deposit():
    if 'user' not in session: return redirect('/login')
    amount = float(request.form['amount'])
    users = load_users()
    user = session['user']
    users[user]['balance'] += amount
    save_users(users)
    log_tx(user, 'deposit', amount)
    flash('Deposit successful.')
    return redirect('/dashboard')

@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'user' not in session: return redirect('/login')
    if request.method == 'POST':
        target = request.form['target']
        amount = float(request.form['amount'])
        pin = request.form['pin']
        user = session['user']
        users = load_users()
        if users[user]['pin'] != hash_pin(pin):
            flash('Incorrect PIN.')
        elif target not in users:
            flash('Target user does not exist.')
        elif users[user]['balance'] < amount:
            flash('Insufficient balance.')
        else:
            users[user]['balance'] -= amount
            users[target]['balance'] += amount
            save_users(users)
            log_tx(user, 'transfer_out', amount, target)
            log_tx(target, 'transfer_in', amount, user)
            flash('Transfer successful.')
            return redirect('/dashboard')
    return render_template_string(transfer_html)

@app.route('/transactions')
def transactions():
    if 'user' not in session: return redirect('/login')
    user = session['user']
    txs = [tx for tx in load_tx() if tx['user'] == user]
    return render_template_string(transactions_html, txs=txs)

@app.route('/delete_account', methods=['GET', 'POST'])
def delete_account():
    if 'user' not in session: return redirect('/login')
    if request.method == 'POST':
        pin = request.form['pin']
        user = session['user']
        users = load_users()
        if users[user]['pin'] == hash_pin(pin):
            del users[user]
            save_users(users)
            flash('Account deleted.')
            session.pop('user', None)
            return redirect('/register')
        else:
            flash('Incorrect PIN.')
    return render_template_string(delete_html)

@app.route('/export')
def export():
    if 'user' not in session: return redirect('/login')
    user = session['user']
    txs = [tx for tx in load_tx() if tx['user'] == user]
    filepath = f"{DATA_DIR}/{user}_transactions.json"
    with open(filepath, 'w') as f:
        json.dump(txs, f, indent=2)
    return send_file(filepath, as_attachment=True)

# --- HTML Templates ---
login_html = '''
<h2>Login</h2>
<form method="post">
  <input name="name" placeholder="Name" required><br>
  <input name="pin" type="password" placeholder="PIN" required><br>
  <button>Login</button>
</form>
<a href="/register">Register</a>
'''

register_html = '''
<h2>Register</h2>
<form method="post">
  <input name="name" placeholder="Name" required><br>
  <input name="pin" type="password" placeholder="PIN" required><br>
  <button>Register</button>
</form>
<a href="/login">Login</a>
'''

dashboard_html = '''
<h2>Welcome {{user}}</h2>
<p>Balance: ₹{{balance}}</p>
<form method="post" action="/deposit">
  <input name="amount" type="number" step="0.01" placeholder="Deposit Amount" required>
  <button>Deposit</button>
</form>
<form method="post" action="/withdraw">
  <input name="amount" type="number" step="0.01" placeholder="Withdraw Amount" required>
  <input name="pin" type="password" placeholder="PIN" required>
  <button>Withdraw</button>
</form>
<a href="/transfer">Transfer</a> |
<a href="/transactions">Transactions</a> |
<a href="/export">Download History</a> |
<a href="/delete_account">Delete Account</a> |
<a href="/logout">Logout</a>
'''

transfer_html = '''
<h2>Transfer Money</h2>
<form method="post">
  <input name="target" placeholder="To (username)" required><br>
  <input name="amount" type="number" step="0.01" placeholder="Amount" required><br>
  <input name="pin" type="password" placeholder="Your PIN" required><br>
  <button>Send</button>
</form>
<a href="/dashboard">Back</a>
'''

transactions_html = '''
<h2>Your Transactions</h2>
<table border="1">
<tr><th>Type</th><th>Amount</th><th>Target</th><th>Date</th></tr>
{% for tx in txs %}
<tr>
  <td>{{tx.type}}</td><td>{{tx.amount}}</td><td>{{tx.target or ''}}</td><td>{{tx.date}}</td>
</tr>
{% endfor %}
</table>
<a href="/dashboard">Back</a>
'''

delete_html = '''
<h2>Delete Account</h2>
<form method="post">
  <input name="pin" type="password" placeholder="Confirm PIN" required>
  <button>Delete</button>
</form>
<a href="/dashboard">Cancel</a>
'''

# --- Run App (Render, Replit, Railway compatible) ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
