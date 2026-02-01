import os
import sqlite3
from main import BankingFlow

def reset_and_seed():
    print("Resetting and seeding database...")
    db_path = "bank_system_v3.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Reset balance to 5000 for test user
    cursor.execute("UPDATE customers SET balance=5000 WHERE account_number='ACC123456'")
    # Clear investments for a clean start
    cursor.execute("DELETE FROM investments WHERE account_number='ACC123456'")
    
    conn.commit()
    conn.close()

def test_investment_validation():
    print("\n--- Testing Investment Validation ---")
    
    # Case 1: Successful investment
    print("\nTEST 1: Valid Investment ($1000)")
    flow1 = BankingFlow()
    flow1.state.account_number = "ACC123456"
    flow1.state.query = "I want to invest $1000 in NVIDIA stocks."
    flow1.kickoff()
    print(f"RESPONSE:\n{flow1.state.response}\n")
    
    # Case 2: Insufficient balance
    print("\nTEST 2: Insufficient Balance (Trying to invest $10000)")
    flow2 = BankingFlow()
    flow2.state.account_number = "ACC123456"
    flow2.state.query = "I want to invest $10000 in Bitcoin."
    flow2.kickoff()
    print(f"RESPONSE:\n{flow2.state.response}\n")

if __name__ == "__main__":
    reset_and_seed()
    test_investment_validation()
