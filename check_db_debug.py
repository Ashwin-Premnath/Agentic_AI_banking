import sqlite3
DB_NAME = "bank_system_v3.db"

def check():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    acc = '6204938206'
    print(f"--- Checking Account: {acc} ---")
    
    cursor.execute("SELECT * FROM customers WHERE account_number=?", (acc,))
    row = cursor.fetchone()
    print(f"Customer: {row}")
    
    cursor.execute("SELECT * FROM investments WHERE account_number=?", (acc,))
    rows = cursor.fetchall()
    print(f"Investments ({len(rows)} found):")
    for r in rows:
        print(f"  {r}")
        
    conn.close()

if __name__ == '__main__':
    check()
