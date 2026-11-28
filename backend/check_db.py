import sqlite3
conn = sqlite3.connect('scamshield.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = cursor.fetchall()
print('Tables:', tables)
for t in tables:
    cursor.execute(f'PRAGMA table_info({t[0]})')
    print(f'\n{t[0]} columns:', [c[1] for c in cursor.fetchall()])
    cursor.execute(f'SELECT COUNT(*) FROM {t[0]}')
    print(f'{t[0]} count:', cursor.fetchone()[0])