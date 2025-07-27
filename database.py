import sqlite3

conn = sqlite3.connect('users.db')
c = conn.cursor()

# Drop old users table if it exists
c.execute("DROP TABLE IF EXISTS users")

# Create new users table with id, coins, level
c.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        coins INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        streak INTEGER DEFAULT 0
    )
''')

conn.commit()
conn.close()
