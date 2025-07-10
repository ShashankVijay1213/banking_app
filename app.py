from flask import Flask, render_template, request, redirect, session, flash, send_file
import os, json, hashlib, datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key'

DATA_DIR = 'data'
USER_FILE = os.path.join(DATA_DIR, 'users.json')
TX_FILE = os.path.join(DATA_DIR, 'transactions.json')

os.makedirs(DATA_DIR, exist_ok=True)
if not os.path.exists(USER_FILE): json.dump({}, open(USER_FILE, 'w'))
if not os.path.exists(TX_FILE): json.dump([], open(TX_FILE, 'w'))

def load_users():
    with open(USER_FILE) as f: return json.load(f)

def save_users(users):
    with open(USER_FILE, 'w') as f: json.dump(users, f, indent=2)

def load_tx():
    with open(TX_FILE) as f: return json.load(f)

def save_tx(txs):
    with open(TX_FILE, 'w') as f: json.dump(txs, f, indent=2)

def hash_pin(pin): return hashlib.sha256(pin.encode()).hexdigest()

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

@app.route('/')
def home(): return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name, pin = request.form['name'], request.form['pin']
        users = load_users()
        if name in users:
            flash('User already exists.')
        else:
            users[name] = {'pin': hash_pin(pin), 'balance': 0}
            save_users(users)
            flash('Registered! Please log in.')
            return redirect('/login')
    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name, pin = request.form['name'], request.form['pin']
        users = load_users()
        if name in users and users[name]['pin'] == hash_pin(pin):
            session['user'] = name
            flash('Login successful.')
            return redirect('/dashboard')
        else:
            flash('Invalid credentials.')
    return render_template("login.html")

@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect('/login')
    user = session['user']
    balance = load_users()[user]['balance']
    return render_template("dashboard.html", user=user, balance=balance)

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out.')
    return redirect('/login')

@app.route('/deposit', methods=['POST'])
def deposit():
    if 'user' not in session: return redirect('/login')
    amount = float(request.form['amount'])
    users = load_users()
    users[session['user']]['balance'] += amount
    save_users(users)
    log_tx(session['user'], 'deposit', amount)
    flash('Deposit successful.')
    return redirect('/dashboard')

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user' not in session: return redirect('/login')
    amount = float(request.form['amount'])
    pin = request.form['pin']
    users = load_users()
    user = session['user']
    if users[user]['pin'] != hash_pin(pin):
        flash('Wrong PIN.')
    elif users[user]['balance'] < amount:
        flash('Insufficient balance.')
    else:
        users[user]['balance'] -= amount
        save_users(users)
        log_tx(user, 'withdraw', amount)
        flash('Withdraw successful.')
    return redirect('/dashboard')

@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'user' not in session: return redirect('/login')
    if request.method == 'POST':
        user = session['user']
        target, amount, pin = request.form['target'], float(request.form['amount']), request.form['pin']
        users = load_users()
        if users[user]['pin'] != hash_pin(pin):
            flash('Wrong PIN.')
        elif target not in users:
            flash('Recipient not found.')
        elif users[user]['balance'] < amount:
            flash('Insufficient funds.')
        else:
            users[user]['balance'] -= amount
            users[target]['balance'] += amount
            save_users(users)
            log_tx(user, 'transfer_out', amount, target)
            log_tx(target, 'transfer_in', amount, user)
            flash('Transfer complete.')
            return redirect('/dashboard')
    return render_template("transfer.html")

@app.route('/transactions')
def transactions():
    if 'user' not in session: return redirect('/login')
    txs = [t for t in load_tx() if t['user'] == session['user']]
    return render_template("transactions.html", txs=txs)

@app.route('/delete_account', methods=['GET', 'POST'])
def delete_account():
    if 'user' not in session: return redirect('/login')
    if request.method == 'POST':
        pin = request.form['pin']
        users = load_users()
        user = session['user']
        if users[user]['pin'] == hash_pin(pin):
            del users[user]
            save_users(users)
            session.pop('user')
            flash('Account deleted.')
            return redirect('/register')
        else:
            flash('Incorrect PIN.')
    return render_template("delete_account.html")

@app.route('/export')
def export():
    if 'user' not in session: return redirect('/login')
    txs = [t for t in load_tx() if t['user'] == session['user']]
    path = f"data/{session['user']}_transactions.json"
    with open(path, 'w') as f: json.dump(txs, f, indent=2)
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
