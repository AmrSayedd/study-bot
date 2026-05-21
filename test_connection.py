"""Run this to verify your Supabase connection works:  python test_connection.py"""

import os, sys

# Paste your full connection string here (with password) for testing
dsn = "postgresql://postgres:YOUR_PASSWORD_HERE@db.abcdefghijklmnopqrst.supabase.co:5432/postgres"

try:
    import psycopg2
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print("Connected!\n" + cur.fetchone()[0])
    cur.execute("CREATE TABLE IF NOT EXISTS test_conn (id SERIAL PRIMARY KEY, val TEXT);")
    cur.execute("INSERT INTO test_conn (val) VALUES ('hello') RETURNING id;")
    print(f"Inserted row with id={cur.fetchone()[0]}")
    cur.execute("DROP TABLE test_conn;")
    conn.commit()
    conn.close()
    print("All good — Supabase connection works!")
except Exception as e:
    print(f"Failed: {e}")
