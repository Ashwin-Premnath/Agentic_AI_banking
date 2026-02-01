import os
import sqlite3
from crews import NL2SQLTool

def test_db_access():
    db_path = "bank_system_v3.db"
    if not os.path.exists(db_path):
        print(f"FAILED: {db_path} not found.")
        return

    print(f"SUCCESS: {db_path} found.")
    
    tool = NL2SQLTool(db_path=db_path)
    
    # Test SELECT
    result = tool._run("SELECT * FROM customers LIMIT 1;")
    print(f"SELECT Result: {result}")
    
    # Test transactions
    result = tool._run("SELECT * FROM transactions LIMIT 1;")
    print(f"Transactions Result: {result}")

if __name__ == "__main__":
    test_db_access()
