import sqlite3
import json

DB_FILENAME = 'blockchain.db'

def init_db():
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            "index" INTEGER,
            timestamp REAL,
            proof INTEGER,
            difficulty INTEGER,
            previous_hash TEXT,
            merkle_root TEXT,
            transactions TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_block(block):
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()
    transactions_json = json.dumps(block['transactions'])
    c.execute('''
        INSERT OR REPLACE INTO blocks ("index", timestamp, proof, previous_hash, difficulty, merkle_root, transactions)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        block['index'],
        block['timestamp'],
        block['proof'],
        block['previous_hash'],
        block['difficulty'],
        block.get('merkle_root', ''),
        transactions_json
    ))
    conn.commit()
    conn.close()

def load_chain():
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()
    c.execute('SELECT index, timestamp, proof, previous_hash, difficulty, merkle_root, transactions FROM blocks ORDER BY idx')
    rows = c.fetchall()
    conn.close()
    chain = []
    for row in rows:
        chain.append({
            'index': row[0],
            'timestamp': row[1],
            'proof': row[2],
            'previous_hash': row[3],
            'difficulty': row[4],
            'merkle_root': row[5],
            'transactions': json.loads(row[6])
        })
    return chain
