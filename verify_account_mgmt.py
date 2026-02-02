import os
import sqlite3
from main import BankingFlow

db_path = "bank_system_v3.db"

def verify_profile_update():
    print("\n--- Testing Account Management Flow ---")
    
    # Use a known account from the DB
    account_num = '6204938206'
    
    # Initial state
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM customers WHERE account_number=?", (account_num,))
    old_email = cursor.fetchone()[0]
    print(f"Old Email: {old_email}")
    conn.close()

    # Request update
    new_email = "new_test_email@example.com"
    flow = BankingFlow()
    flow.state.account_number = account_num
    flow.state.query = f"Please update my email to {new_email}"
    
    try:
        flow.kickoff()
        print(f"RESPONSE:\n{flow.state.response}\n")
        
        # Verify in DB
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM customers WHERE account_number=?", (account_num,))
        updated_email = cursor.fetchone()[0]
        print(f"Updated Email in DB: {updated_email}")
        conn.close()
        
        if updated_email == new_email:
            print("SUCCESS: Profile updated and persisted!")
        else:
            print("FAILURE: Profile update not persisted.")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    verify_profile_update()
