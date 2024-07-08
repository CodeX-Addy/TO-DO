from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'b59346afcc6894694975ade6406cc47885b3ec4be1cd567810e41c9fa0683b2d'

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    todos = conn.execute('SELECT * FROM todos WHERE user_id = ? ORDER BY deadline', (user_id,)).fetchall()
    notifications = conn.execute('SELECT * FROM notifications WHERE user_id = ? AND is_read = 0', (user_id,)).fetchall()
    conn.close()
    return render_template('index.html', todos=todos, notifications=notifications)

@app.route('/add', methods=('GET', 'POST'))
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        deadline = request.form['deadline']
        user_id = session['user_id']
        created_at = datetime.now()

        if not title or not deadline:
            flash('Title and deadline are required!')
        else:
            conn = get_db_connection()
            conn.execute('INSERT INTO todos (title, deadline, user_id, created_at) VALUES (?, ?, ?, ?)', (title, deadline, user_id, created_at))
            conn.execute('INSERT INTO notifications (user_id, message) VALUES (?, ?)', (user_id, f'New to-do item added: {title} with deadline {deadline}'))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))

    return render_template('add.html')

@app.route('/edit/<int:id>', methods=('GET', 'POST'))
def edit(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    todo = conn.execute('SELECT * FROM todos WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        title = request.form['title']
        deadline = request.form['deadline']
        user_id = session['user_id']

        if not title or not deadline:
            flash('Title and deadline are required!')
        else:
            conn.execute('UPDATE todos SET title = ?, deadline = ? WHERE id = ?', (title, deadline, id))
            conn.execute('INSERT INTO notifications (user_id, message) VALUES (?, ?)', (user_id, f'To-do item updated: {title} with new deadline {deadline}'))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))

    conn.close()
    return render_template('edit.html', todo=todo)

@app.route('/delete/<int:id>', methods=('POST',))
def delete(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM todos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password!')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/notifications/mark_as_read/<int:id>', methods=('POST',))
def mark_as_read(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

def send_notification(user_id, message):
    conn = get_db_connection()
    conn.execute('INSERT INTO notifications (user_id, message) VALUES (?, ?)', (user_id, message))
    conn.commit()
    conn.close()

def notify_deadlines():
    while True:
        conn = get_db_connection()
        todos = conn.execute('SELECT * FROM todos').fetchall()
        now = datetime.now()
        for todo in todos:
            deadline = datetime.strptime(todo['deadline'], '%Y-%m-%dT%H:%M')
            if deadline <= now + timedelta(minutes=10) and deadline > now:
                user_id = todo['user_id']
                message = f'Task "{todo["title"]}" is due at {deadline.strftime("%Y-%m-%d %H:%M")}'
                send_notification(user_id, message)
        conn.close()
        time.sleep(60)

if __name__ == "__main__":
    notification_thread = threading.Thread(target=notify_deadlines)
    notification_thread.daemon = True
    notification_thread.start()
    app.run(debug=True, host='0.0.0.0')
