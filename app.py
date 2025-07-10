from flask import Flask, render_template_string, request, redirect, session, flash, send_file
import hashlib, json, os, io, csv

app = Flask(__name__)
app.secret_key = 'secret_key'

USER_FILE = 'users.json'
TX_FILE = 'transactions.json'

# ------------------ Utilities ------------------

def load_users():
    return json.load(open(USER_FILE)) if os.path.exists(USER_FILE) else {}

def save_users(users):
    json.dump(users, open(USER_FILE, 'w'))

def load_transactions():
    return json.load(open(TX_FILE)) if os.path.exists(TX_FILE) else []

def save_transactions(tx):
    json.dump(tx, open(TX_FILE, 'w'))

def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

# ------------------ Template Base ------------------

base = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Bank App</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-4">
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <div class="alert alert-warning">{{ messages[0] }}</div>
    {% endif %}
  {% endwith %}
  {{ content|safe }}
</div>
</body>
</html>
'''

nav = '''
<nav class="nav mb-3">
  <a class="nav-link" href="/dashboard">🏠 Dashboard</a>
  <a class="nav-link" href="/profile">👤 Profile</a>
  <a class="nav-link" href="/transactions">📄 Transactions</a>
  <a class="nav-link" href="/transfer">🔁 Transfer</a>
  <a class="nav-link" href="/export">⬇️ Export</a>
  <a class="nav-link text-danger" href="/delete_account">🗑️ Delete Account</a>
  <a class="nav-link text-secondary" href="/logout">🚪 Logout</a>
</nav>
'''

# ------------------ Helper ------------------

def render(content): return render_template_string(base, content=content)

# ------------------ Routes ------------------

@app.route('/')
def home(): return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = load_users()
        u, p = request.form['username'], request.form['pin']
        if u in users:
            flash("Username exists.")
        else:
            users[u] = {'pin': hash_pin(p), 'balance': 0.0}
            save_users(users)
            flash("Registered successfully.")
            return redirect('/login')
    return render('''<h2>Register</h2><form method="post" class="card p-4 bg-white shadow-sm">
  <input class="form-control mb-2" name="username" placeholder="Username" required>
  <input class="form-control mb-2" name="pin" type="password" placeholder="PIN" required>
  <button class="btn btn-primary">Register</button></form>
  <p class="mt-2"><a href="/login">Already have an account?</a></p>
''')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = load_users()
        u, p = request.form['username'], request.form['pin']
        if u in users and users[u]['pin'] == hash_pin(p):
            session['user'] = u
            return redirect('/dashboard')
        flash("Invalid credentials")
    return render('''<h2>Login</h2><form method="post" class="card p-4 bg-white shadow-sm">
  <input class="form-control mb-2" name="username" placeholder="Username" required>
  <input class="form-control mb-2" name="pin" type="password" placeholder="PIN" required>
  <button class="btn btn-success">Login</button></form>
  <p class="mt-2"><a href="/register">Create an account</a></p>
''')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect('/login')
    u = session['user']
    balance = load_users()[u]['balance']
    return render(f'''{nav}<h3>Welcome, {u}</h3><p>Current Balance: <strong>${balance:.2f}</strong></p>
<form method="post" action="/deposit" class="row g-2">
  <div class="col-md-4"><input name="amount" step="0.01" type="number" class="form-control" placeholder="Deposit amount"></div>
  <div class="col-md-2"><button class="btn btn-primary">Deposit</button></div>
</form>
<form method="post" action="/withdraw" class="row g-2 mt-2">
  <div class="col-md-3"><input name="amount" step="0.01" type="number" class="form-control" placeholder="Withdraw amount"></div>
  <div class="col-md-3"><input name="pin" type="password" class="form-control" placeholder="PIN"></div>
  <div class="col-md-2"><button class="btn btn-warning">Withdraw</button></div>
</form>
''')

@app.route('/deposit', methods=['POST'])
def deposit():
    if 'user' not in session: return redirect('/login')
    amt = float(request.form['amount'])
    u = session['user']
    users = load_users(); tx = load_transactions()
    users[u]['balance'] += amt
    tx.append({'user': u, 'type': 'deposit', 'amount': amt})
    save_users(users); save_transactions(tx)
    return redirect('/dashboard')

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user' not in session: return redirect('/login')
    amt = float(request.form['amount'])
    pin = request.form.get('pin')
    u = session['user']
    users = load_users(); tx = load_transactions()
    if hash_pin(pin) != users[u]['pin']:
        flash("Incorrect PIN.")
    elif users[u]['balance'] >= amt:
        users[u]['balance'] -= amt
        tx.append({'user': u, 'type': 'withdraw', 'amount': amt})
        save_users(users); save_transactions(tx)
        flash("Withdrawal successful.")
    else:
        flash("Insufficient funds.")
    return redirect('/dashboard')

@app.route('/transactions')
def transactions():
    if 'user' not in session: return redirect('/login')
    u = session['user']
    tx = [t for t in load_transactions() if t['user'] == u or t.get('to') == u]
    rows = ''.join(f"<li>{t['type'].capitalize()} - ${t['amount']} {'to '+t['to'] if 'to' in t else ''}</li>" for t in tx)
    return render(f'''{nav}<h3>Your Transactions</h3><ul class="list-group">{rows}</ul>
''')

@app.route('/profile')
def profile():
    if 'user' not in session: return redirect('/login')
    u = session['user']
    balance = load_users()[u]['balance']
    return render(f'''{nav}<h3>Profile</h3><p>Username: <strong>{u}</strong></p><p>Balance: <strong>${balance:.2f}</strong></p>
''')

@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'user' not in session: return redirect('/login')
    u = session['user']
    users = load_users(); tx = load_transactions()
    if request.method == 'POST':
        to = request.form['to_user']
        amt = float(request.form['amount'])
        pin = request.form['pin']
        if hash_pin(pin) != users[u]['pin']:
            flash("Incorrect PIN.")
        elif to not in users:
            flash("User not found.")
        elif to == u:
            flash("Cannot send to yourself.")
        elif users[u]['balance'] < amt:
            flash("Insufficient funds.")
        else:
            users[u]['balance'] -= amt
            users[to]['balance'] += amt
            tx.append({'user': u, 'type': 'transfer', 'amount': amt, 'to': to})
            save_users(users); save_transactions(tx)
            flash("Transfer successful.")
            return redirect('/dashboard')
    return render(f'''{nav}<h3>Transfer Money</h3><form method="post" class="card p-4 bg-white shadow-sm">
  <input name="to_user" class="form-control mb-2" placeholder="Recipient Username" required>
  <input name="amount" step="0.01" type="number" class="form-control mb-2" placeholder="Amount" required>
  <input name="pin" type="password" class="form-control mb-2" placeholder="Enter PIN" required>
  <button class="btn btn-secondary">Send</button></form>
''')

@app.route('/export')
def export():
    if 'user' not in session: return redirect('/login')
    u = session['user']
    tx = [t for t in load_transactions() if t['user'] == u or t.get('to') == u]
    output = io.StringIO()
    csv.DictWriter(output, fieldnames=['user', 'type', 'amount', 'to']).writerows(tx)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='transactions.csv')

@app.route('/delete_account', methods=['GET', 'POST'])
def delete_account():
    if 'user' not in session: return redirect('/login')
    u = session['user']; users = load_users(); tx = load_transactions()
    if request.method == 'POST':
        pin = request.form.get('pin')
        if hash_pin(pin) != users[u]['pin']:
            flash("Incorrect PIN.")
            return redirect('/delete_account')
        users.pop(u)
        tx = [t for t in tx if t['user'] != u and t.get('to') != u]
        save_users(users); save_transactions(tx); session.pop('user')
        flash("Account deleted.")
        return redirect('/register')
    return render(f'''{nav}<h3>Delete Account</h3><p>This action is <strong>irreversible</strong>.</p>
<form method="post" class="card p-4 bg-white shadow-sm">
  <input name="pin" class="form-control mb-2" placeholder="Enter your PIN to confirm" type="password" required>
  <button class="btn btn-danger">Delete My Account</button></form>
''')

if __name__ == '__main__':
    app.run(debug=True)
