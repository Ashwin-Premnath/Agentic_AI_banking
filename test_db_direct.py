import sqlite3
import os

db_path = "bank_system_v3.db"

def test_db_updates():
    print(f"Testing database updates on {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Check initial balance
    account_num = '6204938206'
    cursor.execute("SELECT balance FROM customers WHERE account_number=?", (account_num,))
    initial_balance = cursor.fetchone()[0]
    print(f"Initial Balance for {account_num}: {initial_balance}")
    
    # 2. Simulate Investment ($500)
    investment_amount = 500.0
    asset_name = "NVIDIA"
    asset_type = "Stock"
    
    print(f"Simulating investment of ${investment_amount} in {asset_name}...")
    
    # Deduct from balance
    cursor.execute("UPDATE customers SET balance = balance - ? WHERE account_number = ?", (investment_amount, account_num))
    # Add to investments
    cursor.execute("INSERT INTO investments (account_number, asset_name, asset_type, invested_amount, current_value) VALUES (?, ?, ?, ?, ?)",
                   (account_num, asset_name, asset_type, investment_amount, investment_amount))
    
    conn.commit()
    
    # 3. Verify changes
    cursor.execute("SELECT balance FROM customers WHERE account_number=?", (account_num,))
    new_balance = cursor.fetchone()[0]
    print(f"New Balance: {new_balance}")
    
    cursor.execute("SELECT * FROM investments WHERE account_number=? AND asset_name='NVIDIA'", (account_num,))
    investment = cursor.fetchone()
    print(f"Investment Record: {investment}")
    
    conn.close()
    
    if new_balance == initial_balance - investment_amount and investment is not None:
        print("\nSUCCESS: Database updates correctly!")
    else:
        print("\nFAILURE: Database updates did not work as expected.")

if __name__ == "__main__":
    test_db_updates()
