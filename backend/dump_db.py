import sqlite3
import json
conn = sqlite3.connect('scamshield.db')
cursor = conn.cursor()

print("=== SCANS ===")
cursor.execute('SELECT * FROM scans')
for row in cursor.fetchall():
    print(row)

print("\n=== EVIDENCE ===")
cursor.execute('SELECT * FROM evidence')
for row in cursor.fetchall():
    print(row)

print("\n=== FEEDBACK ===")
cursor.execute('SELECT * FROM feedback')
for row in cursor.fetchall():
    print(row)