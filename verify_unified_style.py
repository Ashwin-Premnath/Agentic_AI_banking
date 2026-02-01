import os
import sqlite3
from main import BankingFlow

def seed_db():
    print("Seeding database with sample data...")
    db_path = "bank_system_v3.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute("SELECT * FROM customers WHERE account_number='ACC123456'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO customers (name, email, account_number, balance) VALUES (?, ?, ?, ?)", 
                       ("Test User", "test@example.com", "ACC123456", 5000.0))
    
    # Add some transactions for spending forecast
    cursor.execute("SELECT count(*) FROM transactions WHERE account_number='ACC123456'")
    if cursor.fetchone()[0] == 0:
        transactions = [
            ("ACC123456", "RECV1", "Debit", "Card", 50.0),
            ("ACC123456", "RECV2", "Debit", "Transfer", 200.0),
            ("ACC123456", "RECV3", "Debit", "Card", 20.0),
        ]
        cursor.executemany("INSERT INTO transactions (account_number, receiver_account_number, transaction_type, mode_of_payment, amount) VALUES (?, ?, ?, ?, ?)", transactions)
    
    conn.commit()
    conn.close()

def test_unified_style():
    print("\n--- Testing Unified Style ---")
    
    queries = [
        "What is my current balance?",
        "How much will I spend next month based on my history?",
        "I want to invest $1000 in Tesla. Show my portfolio and forecast."
    ]
    
    for query in queries:
        print(f"\nProcessing: {query}")
        flow = BankingFlow()
        flow.state.account_number = "ACC123456"
        flow.state.query = query
        try:
            flow.kickoff()
            print(f"RESPONSE:\n{flow.state.response}\n")
            print("-" * 30)
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    seed_db()
    test_unified_style()
