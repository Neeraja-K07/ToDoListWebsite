from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 🔐 Required for session and flash

# Ensure todolist table exists
def init_todolist_table():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS todolist (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            date_time DATETIME NOT NULL,
            user_id INTEGER NOT NULL,
            recycled BOOLEAN DEFAULT 0,
            completed BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()


@app.route('/delete_habit', methods=['POST'])
def delete_habit():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.get_json()
    habit_id = data.get('habit_id')

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        DELETE FROM habits WHERE habit_id = ? AND user_id = ?
    ''', (habit_id, session['user_id']))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Habit deleted successfully'})






# Signup route
@app.route('/signup', methods=['POST'])
def signup():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']

    hashed_password = generate_password_hash(password)

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                  (username, email, hashed_password))
        conn.commit()
        flash('Signup successful! Please login.', 'success')
    except sqlite3.IntegrityError:
        flash('Username or email already exists.', 'error')
    conn.close()
    
    return redirect(url_for('show_auth'))

# Login route with session tracking
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, password, coins, level FROM users WHERE username = ?", (username,))

    row = c.fetchone()
    conn.close()

    if row and check_password_hash(row[1], password):
        session['user_id'] = row[0]
        session['username'] = username
        session['coins'] = row[2]
        session['level'] = row[3]

        flash('Login successful!', 'success')
        return redirect(url_for('index'))
    else:
        flash('Invalid credentials.', 'error')
        return redirect(url_for('show_auth'))

# Route to add a task (from JS fetch or form)
@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    task = request.form.get('task')
    date_time = request.form.get('date_time')

    if not task or not date_time:
        return jsonify({'error': 'Task or date/time missing'}), 400

    init_todolist_table()

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO todolist (item, date_time, user_id)
        VALUES (?, ?, ?)
    ''', (task, date_time, session['user_id']))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Task added successfully'})

# Route to get tasks for the logged-in user
@app.route('/get_tasks')
def get_tasks():
    if 'user_id' not in session:
        return jsonify([])

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        SELECT item_id, item, date_time, completed, recycled
        FROM todolist
        WHERE user_id = ? AND recycled = 0
        ORDER BY date_time ASC
    ''', (session['user_id'],))
    tasks = c.fetchall()
    conn.close()

    task_list = [{
        'id': row[0],
        'text': row[1],
        'datetime': row[2],
        'completed': bool(row[3]),
        'recycled': bool(row[4])
    } for row in tasks]

    return jsonify(task_list)

# Mark task as completed/uncompleted
@app.route('/complete_task', methods=['POST'])
def complete_task():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.get_json()
    task_id = data.get('task_id')
    completed = 1 if data.get('completed') else 0

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        UPDATE todolist SET completed = ?
        WHERE item_id = ? AND user_id = ?
    ''', (completed, task_id, session['user_id']))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Task completion status updated'})

# Soft delete: move task to recycle bin
@app.route('/recycle_task', methods=['POST'])
def recycle_task():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.get_json()
    task_id = data.get('task_id')

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        UPDATE todolist SET recycled = 1
        WHERE item_id = ? AND user_id = ?
    ''', (task_id, session['user_id']))
    conn.commit()
    conn.close()

    print(f"[DEBUG] Task {task_id} recycled by user {session['user_id']}")  # Add this line

    return jsonify({'message': 'Task moved to recycle bin'})


@app.route('/get_recycled_tasks')
def get_recycled_tasks():
    if 'user_id' not in session:
        return jsonify([])

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        SELECT item_id, item, date_time
        FROM todolist
        WHERE user_id = ? AND recycled = 1
        ORDER BY date_time ASC
    ''', (session['user_id'],))
    tasks = c.fetchall()
    conn.close()

    task_list = [{
        'id': row[0],
        'text': row[1],
        'datetime': row[2]
    } for row in tasks]

    return jsonify(task_list)

@app.route('/clear_recycle_bin', methods=['POST'])
def clear_recycle_bin():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authorized'}), 401

    user_id = session['user_id']
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('DELETE FROM todolist WHERE user_id = ? AND recycled = 1', (user_id,))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Recycle bin cleared'})


# Logout route to clear session
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('show_auth'))

# Routes
@app.route("/")
def home():
    return render_template("landing.html")

@app.route("/todo")
def todo():
    return render_template("todo.html")

@app.route("/auth")
def show_auth():
    return render_template("auth.html")



import random

@app.route("/index")
def index():
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('show_auth'))
    
    username = session.get('username')

    # 100 cute motivational quotes
    quotes = [
        "Believe in yourself and all that you are. 💖",
        "Small steps every day lead to big changes. 🌱",
        "Be a voice, not an echo. 🐰",
        "Happiness is a habit—cultivate it. 🌸",
        "Dream big, sparkle more, shine bright. ✨",
        "You are stronger than you think. 🐻",
        "Today is your day! 🌈",
        "You’ve got this, darling. 🍓",
        "Focus on the good. 💕",
        "Keep growing. 🌻",
        "Your only limit is your mind. 🌟",
        "Be kind to yourself. 🌼",
        "Cute things happen when you smile. 🧁",
        "Progress, not perfection. 🍥",
        "One habit at a time. 💪",
        "Let your dreams blossom. 🌷",
        "Take it easy, but take it. 🐢",
        "Little things make big days. 🌸",
        "Enjoy the little moments. 🍡",
        "Every day is a fresh start. 🧸",
        "Don’t quit. You’re almost there. 🌤️",
        "You are doing better than you think. 💌",
        "Do it for your future self. 🍰",
        "Wake up and be fabulous. 💃",
        "Stay soft. It looks good on you. 🐇",
        "Let your heart be your compass. 🧭",
        "You sparkle from the inside. 💫",
        "Trust the process. 🍒",
        "Celebrate your tiny victories. 🥳",
        "You’re a work in progress and that’s okay. 💗",
        "Even the moon goes through phases. 🌙",
        "Be gentle with yourself. 💕",
        "The world needs your magic. 🦄",
        "Shine like the whole universe is yours. ✨",
        "Success is a series of small wins. 🧃",
        "Your vibes attract your tribe. 🐝",
        "Start where you are. Use what you have. 🛠️",
        "You’re made of stardust. 🌠",
        "Cute things take time. 🐣",
        "One day or day one—you decide. 📅",
        "Smile more, worry less. 🐶",
        "You are your only limit. 🐾",
        "Keep going even if it’s slow. 🐌",
        "It’s okay to rest. 🍩",
        "Create a life you love. 🌼",
        "Your journey is unique. 🗺️",
        "Today is full of possibilities. 🎈",
        "You make the world cuter. 🐰",
        "Keep your chin up, buttercup. 🌼",
        "You’re magic. Don’t forget it. 🧚",
        "Do it with love. 💖",
        # Add 50 more if needed
    ]

    # Get quote based on user_id and today's date (so same user gets same quote each day)
    user_id = session['user_id']
    today = datetime.now().date().isoformat()
    index = (user_id + sum(ord(c) for c in today)) % len(quotes)
    quote = quotes[index]

    return render_template("index.html", username=username, quote=quote)
    


@app.route("/resetpassword")
def reset_password():
    return render_template("resetpassword.html")



# Add this with the other table initializations
def init_calendar_table():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS calendar (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event TEXT NOT NULL,
            event_date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()


# Route to add a calendar event
@app.route('/add_event', methods=['POST'])
def add_event():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    event = request.form.get('event')
    event_date = request.form.get('event_date')  # Expected format: YYYY-MM-DD

    if not event or not event_date:
        return jsonify({'error': 'Missing event or date'}), 400

    init_calendar_table()
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO calendar (user_id, event, event_date)
        VALUES (?, ?, ?)
    ''', (session['user_id'], event, event_date))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Event added successfully'})


# Route to get events for a specific date
@app.route('/get_events/<date>')
def get_events(date):
    if 'user_id' not in session:
        return jsonify([])

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        SELECT event_id, event, event_date
        FROM calendar
        WHERE user_id = ? AND event_date = ?
    ''', (session['user_id'], date))
    events = c.fetchall()
    conn.close()

    event_list = [{
        'id': row[0],
        'event': row[1],
        'date': row[2]
    } for row in events]

    return jsonify(event_list)


def init_habits_table():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS habits (
            habit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            habit TEXT NOT NULL,
            completed BOOLEAN DEFAULT 0,
            due_time DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/add_habit', methods=['POST'])
def add_habit():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    habit = request.form.get('habit')
    due_time = request.form.get('due_time')

    if not habit or not due_time:
        return jsonify({'error': 'Missing habit or time'}), 400

    init_habits_table()
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO habits (user_id, habit, due_time)
        VALUES (?, ?, ?)
    ''', (session['user_id'], habit, due_time))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Habit added successfully'})







# @app.route('/get_habits')
# def get_habits():
#     if 'user_id' not in session:
#         return jsonify([])

#     init_habits_table()
#     conn = sqlite3.connect('users.db')
#     c = conn.cursor()
#     c.execute('''
#         SELECT habit_id, habit, completed, due_time
#         FROM habits
#         WHERE user_id = ?
#         ORDER BY due_time ASC
#     ''', (session['user_id'],))
#     rows = c.fetchall()
#     conn.close()

#     return jsonify([
#         {
#             'id': row[0],
#             'habit': row[1],
#             'completed': bool(row[2]),
#             'due_time': row[3],
#             'can_check': datetime.now() < datetime.fromisoformat(row[3])
#         }
#         for row in rows
#     ])

from datetime import datetime

@app.route('/get_habits')
def get_habits():
    if 'user_id' not in session:
        return jsonify([])

    init_habits_table()
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        SELECT habit_id, habit, completed, due_time
        FROM habits
        WHERE user_id = ?
        ORDER BY due_time ASC
    ''', (session['user_id'],))
    rows = c.fetchall()
    conn.close()

    now_time = datetime.now().time()

    habits = []
    for row in rows:
        due_dt = datetime.fromisoformat(row[3])
        due_time_only = due_dt.time()

        can_check = (not row[2]) and (now_time < due_time_only)

        print(f"DEBUG: habit={row[1]}, now={now_time}, due={due_time_only}, completed={row[2]}, can_check={can_check}")

        habits.append({
            'id': row[0],
            'habit': row[1],
            'completed': bool(row[2]),
            'due_time': row[3],
            'can_check': can_check
        })

    return jsonify(habits)



@app.route('/complete_habit', methods=['POST'])
def complete_habit():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.get_json()
    habit_id = data.get('habit_id')

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        UPDATE habits SET completed = 1
        WHERE habit_id = ? AND user_id = ?
    ''', (habit_id, session['user_id']))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Habit marked as completed'})



@app.route('/get_event_dates')
def get_event_dates():
    if 'user_id' not in session:
        return jsonify([])

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        SELECT DISTINCT event_date
        FROM calendar
        WHERE user_id = ?
    ''', (session['user_id'],))
    rows = c.fetchall()
    conn.close()

    event_dates = [row[0] for row in rows]
    return jsonify(event_dates)

@app.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    try:
        print(f"➡️ Received request to delete event ID: {event_id}")
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM calendar WHERE event_id = ?', (event_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print('❌ Delete Error:', e)
        return jsonify({'success': False}), 500




@app.route('/update_task', methods=['POST'])
def update_task():
    data = request.get_json()
    print("🔧 Received data in update_task:", data)

    task_id = data.get('task_id')
    new_text = data.get('new_text')
    new_datetime = data.get('new_datetime')

    if not all([task_id, new_text, new_datetime]):
        print(f"❌ Missing fields: {task_id} {new_text} {new_datetime}")
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        # ✅ Use correct column names from your schema
        c.execute('''
            UPDATE todolist
            SET item = ?, date_time = ?
            WHERE item_id = ?
        ''', (new_text, new_datetime, task_id))

        conn.commit()
        conn.close()

        print(f"✅ Task {task_id} updated successfully")
        return jsonify({'status': 'success'}), 200

    except Exception as e:
        print(f"❌ Error updating task: {e}")
        return jsonify({'status': 'error', 'message': 'Database error'}), 500

@app.route('/get_user_settings')
def get_user_settings():
    print("=== DEBUG: /get_user_settings endpoint hit ===")
    print("DEBUG: Current session ->", dict(session))

    if 'user_id' not in session:
        print("DEBUG: No user_id found in session")
        return jsonify({'error': 'Not logged in'}), 401

    user_id = session['user_id']
    print("DEBUG: Session user_id =", session.get('user_id'))

    print(f"DEBUG: Fetching settings for user_id={user_id}")

    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT username, email, coins, level, streak FROM users WHERE id = ?', (user_id,))
        row = c.fetchone()
        conn.close()

        print("DEBUG: SQL query result ->", row)

        if not row:
            print(f"DEBUG: No user found for id={user_id}")
            return jsonify({'error': 'User not found'}), 404

        result = {
            'username': row[0],
            'email': row[1],
            'coins': row[2],
            'level': row[3],
            'streak': row[4] or 0  # fallback to 0 if None
        }
        print("DEBUG: Returning user settings ->", result)
        return jsonify(result)

    except Exception as e:
        import traceback
        print("❌ ERROR in get_user_settings:", e)
        print(traceback.format_exc())
        return jsonify({'error': 'Server error'}), 500


def check_and_update_streaks():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Get all users
    c.execute("SELECT id FROM users")
    users = c.fetchall()

    for (user_id,) in users:
        # ✅ Count all habits for this user (ignores date)
        c.execute('''
            SELECT COUNT(*) FROM habits 
            WHERE user_id = ?
        ''', (user_id,))
        total_habits = c.fetchone()[0]

        # ✅ Count completed habits (ignores date)
        c.execute('''
            SELECT COUNT(*) FROM habits 
            WHERE user_id = ? AND completed = 1
        ''', (user_id,))
        completed_habits = c.fetchone()[0]

        if total_habits > 0 and total_habits == completed_habits:
            # Increment streak if all habits are completed
            c.execute('UPDATE users SET streak = streak + 1 WHERE id = ?', (user_id,))

        # ✅ Reset all habits regardless of date
        c.execute('''
            UPDATE habits SET completed = 0
            WHERE user_id = ?
        ''', (user_id,))
        print(f"DEBUG: Reset completed for user_id={user_id}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_update_streaks, 'cron', hour=12, minute=11)
    scheduler.start()

    import atexit
    atexit.register(lambda: scheduler.shutdown())

    app.run(debug=True, use_reloader=False)