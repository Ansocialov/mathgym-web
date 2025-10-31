from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import sqlite3
import hashlib
import random
from fractions import Fraction
import re
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "mathgym_secure_key_2025"

DB = "mathgym.db"

# ---------------------------
# Вспомогательные функции
# ---------------------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            stars INTEGER DEFAULT 0,
            last_active TEXT
        )
    ''')
    dev_hash = hashlib.sha256("dev12345678".encode()).hexdigest()
    try:
        c.execute("INSERT INTO users (username, password_hash, stars) VALUES (?, ?, ?)",
                  ("Developer", dev_hash, 9999))
    except:
        pass
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def validate_username(username):
    return bool(username and username[0].isupper() and not re.search(r'\d', username))

def validate_password(password):
    return len(password) >= 8 and sum(1 for c in password if c.isalpha() and c.isascii()) >= 2

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ---------------------------
# Генераторы задач
# ---------------------------
def generate_equation_task():
    a, b, c = random.randint(2, 10), random.randint(1, 15), random.randint(10, 50)
    x = (c - b) / a
    return f"Решите уравнение: {a}x + {b} = {c}", x, f"x = ({c} - {b}) / {a}"

def generate_fraction_task():
    a, b = random.randint(1, 10), random.randint(2, 12)
    c, d = random.randint(1, 10), random.randint(2, 12)
    res = Fraction(a, b) + Fraction(c, d)
    return f"Вычислите: {a}/{b} + {c}/{d}", float(res), f"Общий знаменатель: {b*d}"

def generate_percent_task():
    total = random.randint(50, 200)
    percent = random.choice([10, 15, 20, 25, 30, 40, 50])
    return f"Найдите {percent}% от {total}", total * percent / 100, f"({percent}/100) × {total}"

def generate_negative_task():
    a, b = random.randint(-20, -1), random.randint(-20, -1)
    op = random.choice(['+', '-', '*', '/'])
    if op == '+': res = a + b
    elif op == '-': res = a - b
    elif op == '*': res = a * b
    else: res = round(a / b, 2) if b != 0 else 0
    return f"Вычислите: ({a}) {op} ({b})", res, f"{a} {op} {b} = {res}"

def generate_geometry_task():
    side = random.randint(5, 15)
    return f"Найдите площадь квадрата со стороной {side} см", side * side, "Площадь = сторона²"

def generate_logic_task():
    x = random.randint(5, 20)
    y = random.randint(2, 5)
    return f"У Пети {x} карандашей. У каждого из {y} друзей в {y} раз больше. Сколько всего?", x + (x * y * y), "Петя + друзья"

ALL_GENERATORS = [
    generate_equation_task,
    generate_fraction_task,
    generate_percent_task,
    generate_negative_task,
    generate_geometry_task,
    generate_logic_task
]

def generate_random_task():
    return random.choice(ALL_GENERATORS)()

# ---------------------------
# Маршруты
# ---------------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not validate_username(username):
            flash("❌ Имя должно начинаться с заглавной буквы и не содержать цифр!", "error")
            return render_template('login.html')
        if not validate_password(password):
            flash("❌ Пароль: минимум 8 символов, 2+ английские буквы", "error")
            return render_template('login.html')
        pwd_hash = hash_password(password)
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ? AND password_hash = ?", (username, pwd_hash)).fetchone()
        if user:
            session['user'] = username
            return redirect(url_for('main'))
        else:
            flash("❌ Неверный логин или пароль", "error")
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username'].strip()
    password = request.form['password']
    if not validate_username(username):
        flash("❌ Имя: заглавная буква, без цифр", "error")
        return render_template('login.html')
    if not validate_password(password):
        flash("❌ Пароль: 8+ символов, 2+ англ. буквы", "error")
        return render_template('login.html')
    pwd_hash = hash_password(password)
    db = get_db()
    try:
        db.execute("INSERT INTO users (username, password_hash, stars) VALUES (?, ?, 0)", (username, pwd_hash))
        db.commit()
        session['user'] = username
        return redirect(url_for('main'))
    except:
        flash("❌ Пользователь уже существует", "error")
        return render_template('login.html')

@app.route('/main')
def main():
    if 'user' not in session:
        return redirect(url_for('login'))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (session['user'],)).fetchone()
    return render_template('main.html', user=user)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/rating')
def rating():
    if 'user' not in session:
        return redirect(url_for('login'))
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY stars DESC LIMIT 50").fetchall()
    return render_template('rating.html', users=users, current=session['user'])

@app.route('/api/update_stars', methods=['POST'])
def api_update_stars():
    if 'user' not in session:
        return jsonify({"error": "Не авторизован"}), 401
    data = request.json
    stars = data.get('stars', 0)
    if not isinstance(stars, int) or stars < 0:
        return jsonify({"error": "Некорректные звёзды"}), 400
    db = get_db()
    db.execute("UPDATE users SET stars = ?, last_active = ? WHERE username = ?", (stars, datetime.now().isoformat(), session['user']))
    db.commit()
    return jsonify({"success": True})

@app.route('/api/delete_user', methods=['POST'])
def api_delete_user():
    if session.get('user') != "Developer":
        return jsonify({"error": "Только Developer может удалять"}), 403
    target = request.json.get('username')
    if target == "Developer":
        return jsonify({"error": "Нельзя удалить Developer"}), 400
    db = get_db()
    db.execute("DELETE FROM users WHERE username = ?", (target,))
    db.commit()
    return jsonify({"success": True})

@app.route('/api/task')
def api_task():
    task, ans, hint = generate_random_task()
    return jsonify({"task": task, "answer": ans, "hint": hint})

@app.route('/mode/<mode_name>')
def mode_page(mode_name):
    if mode_name not in ['speed', 'hard', 'marathon']:
        return redirect(url_for('main'))
    if 'user' not in session:
        return redirect(url_for('login'))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (session['user'],)).fetchone()
    return render_template('task_modes.html', mode=mode_name, user=user)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)