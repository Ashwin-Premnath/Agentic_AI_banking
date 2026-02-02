import sqlite3
from datetime import datetime
import random
import time
from faker import Faker

fake = Faker()

DB_NAME = "bank_system_v3.db"

def adapt_datetime_iso(val):
    """Adapt datetime.datetime to timezone-naive ISO 8601 string."""
    return val.isoformat()

def convert_datetime(val):
    """Convert ISO 8601 string to datetime.datetime object."""
    return datetime.fromisoformat(val.decode() if isinstance(val, bytes) else val)

# 1. Register the adapter: Handles Saving (Python Object -> SQL String)
sqlite3.register_adapter(datetime, adapt_datetime_iso)

# 2. Register the converter: Handles Reading (SQL String -> Python Object)
sqlite3.register_converter("TIMESTAMP", convert_datetime)

# ==========================================================

def initialize_database():
    """
    Connects to the database, creates tables.
    Uses detect_types to ensure the converter works if we read data back.
    """
    # detect_types=sqlite3.PARSE_DECLTYPES is crucial for the converter
    conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()

    # Drop tables to ensure clean schema with updated columns
    cursor.execute('DROP TABLE IF EXISTS transactions')
    cursor.execute('DROP TABLE IF EXISTS customers')

    # 1. Create Customers Table
    cursor.execute('''
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            account_number TEXT UNIQUE NOT NULL,
            balance REAL DEFAULT 1000.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Create Transactions Table
    cursor.execute('''
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT NOT NULL,
            receiver_account_number TEXT,
            transaction_type TEXT NOT NULL,
            mode_of_payment TEXT NOT NULL,
            amount REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_number) REFERENCES customers (account_number)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"[*] Database '{DB_NAME}' initialized successfully.")

def generate_fake_customers(num_customers=100):
    """
    Generates fake customer data.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print(f"[*] Generating {num_customers} fake customers...")
    
    for _ in range(num_customers):
        name = fake.name()
        email = fake.email()
        account_number = fake.numerify(text='##########')
        balance = round(random.uniform(500, 5000), 2)
        
        try:
            cursor.execute('''
                INSERT INTO customers (name, email, account_number, balance)
                VALUES (?, ?, ?, ?)
            ''', (name, email, account_number, balance))
        except sqlite3.IntegrityError:
            continue

    conn.commit()
    conn.close()
    print("[*] Customer generation complete.")

def get_random_account(cursor):
    """Helper to fetch a random account."""
    cursor.execute("SELECT account_number, balance FROM customers ORDER BY RANDOM() LIMIT 1")
    return cursor.fetchone()

def simulate_realtime_transactions():
    """
    Simulates Withdrawals, Deposits, and Transfers.
    Uses datetime objects directly, relying on the registered adapter.
    """
    # detect_types=sqlite3.PARSE_DECLTYPES allows reading datetimes back as objects
    conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    
    print("[*] Starting real-time transaction simulation (Python 3.12 Compliant)...")
    print("[*] Press Ctrl+C to stop.")
    print("-" * 80)

    try:
        while True:
            cursor = conn.cursor()
            
            # Pick a primary account
            sender_data = get_random_account(cursor)
            if not sender_data:
                continue
            
            sender_acc, sender_bal = sender_data
            
            # Define Probabilities for Transaction Types
            action = random.choices(
                ['WITHDRAWAL', 'DEPOSIT', 'TRANSFER'], 
                weights=[0.4, 0.4, 0.2]
            )[0]

            receiver_acc = None
            mode = ""
            amount = 0
            valid = False

            # GET CURRENT TIME AS DATETIME OBJECT
            # The adapter registered at the top of the script handles the conversion
            current_timestamp = datetime.now() 

            # --- LOGIC: WITHDRAWAL ---
            if action == 'WITHDRAWAL':
                modes = ['ATM', 'POS (Point of Sale)', 'Credit Card Payment', 'Bank Check']
                mode = random.choice(modes)
                
                amount = round(random.uniform(10, min(sender_bal * 0.3, 1000)), 2)
                
                if sender_bal >= amount:
                    new_bal = sender_bal - amount
                    cursor.execute("UPDATE customers SET balance = ? WHERE account_number = ?", (new_bal, sender_acc))
                    
                    # Inserting raw datetime object (No warning!)
                    cursor.execute('''INSERT INTO transactions 
                        (account_number, receiver_account_number, transaction_type, mode_of_payment, amount, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)''', 
                        (sender_acc, None, 'WITHDRAWAL', mode, amount, current_timestamp))
                    valid = True

            # --- LOGIC: DEPOSIT ---
            elif action == 'DEPOSIT':
                modes = ['Cash Deposit', 'Salary Transfer', 'Direct Deposit', 'Check Clear']
                mode = random.choice(modes)
                
                amount = round(random.uniform(50, 2000), 2)
                
                new_bal = sender_bal + amount
                cursor.execute("UPDATE customers SET balance = ? WHERE account_number = ?", (new_bal, sender_acc))
                
                # Inserting raw datetime object
                cursor.execute('''INSERT INTO transactions 
                    (account_number, receiver_account_number, transaction_type, mode_of_payment, amount, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)''', 
                    (sender_acc, None, 'DEPOSIT', mode, amount, current_timestamp))
                valid = True

            # --- LOGIC: TRANSFER ---
            elif action == 'TRANSFER':
                receiver_data = get_random_account(cursor)
                if receiver_data:
                    receiver_acc, receiver_bal = receiver_data
                    
                    if receiver_acc != sender_acc:
                        modes = ['UPI', 'IMPS', 'NEFT', 'RTGS']
                        mode = random.choice(modes)
                        
                        amount = round(random.uniform(100, min(sender_bal * 0.5, 5000)), 2)
                        
                        if sender_bal >= amount:
                            sender_new_bal = sender_bal - amount
                            cursor.execute("UPDATE customers SET balance = ? WHERE account_number = ?", (sender_new_bal, sender_acc))
                            
                            receiver_new_bal = receiver_bal + amount
                            cursor.execute("UPDATE customers SET balance = ? WHERE account_number = ?", (receiver_new_bal, receiver_acc))
                            
                            # Inserting raw datetime object
                            cursor.execute('''INSERT INTO transactions 
                                (account_number, receiver_account_number, transaction_type, mode_of_payment, amount, timestamp)
                                VALUES (?, ?, ?, ?, ?, ?)''', 
                                (sender_acc, receiver_acc, 'TRANSFER', mode, amount, current_timestamp))
                            
                            valid = True

            if valid:
                conn.commit()
                
                # Get updated balance for display
                cursor.execute("SELECT balance FROM customers WHERE account_number = ?", (sender_acc,))
                current_bal_display = cursor.fetchone()[0]

                timestamp_str = datetime.now().strftime("%H:%M:%S")
                receiver_str = f"-> Acc: {receiver_acc}" if receiver_acc else "-> External/Merchant"
                
                print(f"[{timestamp_str}] {action} ({mode}) | Sender: {sender_acc} {receiver_str} | Amt: ${amount:.2f} | Bal: ${current_bal_display:.2f}")

                # Random sleep for realism
                time.sleep(random.uniform(0.2, 2.0))

    except KeyboardInterrupt:
        print("\n[*] Simulation stopped.")
    finally:
        conn.close()

if __name__ == "__main__":
    initialize_database()
    generate_fake_customers(num_customers=50)
    simulate_realtime_transactions()