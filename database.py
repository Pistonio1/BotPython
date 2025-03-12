import sqlite3

def init_db():
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()

    # Создание таблиц
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 id INTEGER PRIMARY KEY,
                 system_id INTEGER UNIQUE,
                 balance REAL DEFAULT 0,
                 ref_code TEXT,
                 ref_count INTEGER DEFAULT 0,
                 role TEXT DEFAULT 'client',
                 banned INTEGER DEFAULT 0,
                 pin TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS categories (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS games (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT,
                 category_id INTEGER,
                 weight TEXT,
                 FOREIGN KEY (category_id) REFERENCES categories(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS products (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 game_id INTEGER,
                 name TEXT,
                 price REAL,
                 code TEXT,
                 FOREIGN KEY (game_id) REFERENCES games(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS purchases (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 product_name TEXT,
                 price REAL,
                 FOREIGN KEY (user_id) REFERENCES users(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS deposit_requests (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 amount REAL,
                 status TEXT,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY (user_id) REFERENCES users(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
                 code TEXT PRIMARY KEY,
                 value REAL,
                 uses INTEGER)''')

    c.execute('''CREATE TABLE IF NOT EXISTS support_requests (
                 request_id TEXT PRIMARY KEY,
                 user_id INTEGER,
                 message TEXT,
                 FOREIGN KEY (user_id) REFERENCES users(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS districts (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT,
                 category_id INTEGER,
                 FOREIGN KEY (category_id) REFERENCES categories(id))''')

    # Проверка и добавление столбца weight в таблице games
    c.execute("PRAGMA table_info(games)")
    columns = [col[1] for col in c.fetchall()]
    if 'weight' not in columns:
        c.execute("ALTER TABLE games ADD COLUMN weight TEXT")

    # Проверка и добавление столбца role в таблице users, если его нет
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    if 'role' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'client'")

    conn.commit()
    conn.close()

def get_db_data(query, params=()):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute(query, params)
    result = c.fetchall()
    conn.close()
    return result

def get_db_single(query, params=()):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute(query, params)
    result = c.fetchone()
    conn.close()
    return result

def execute_db(query, params=()):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()