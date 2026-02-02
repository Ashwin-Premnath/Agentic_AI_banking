import os
from main import BankingFlow

def test_investment_flow():
    print("\n--- Testing Investment Flow ---")
    flow = BankingFlow()
    flow.state.account_number = "ACC123456"
    flow.state.query = "I want to invest $1000 in Apple stocks. Record this and show my forecast."
    flow.kickoff()
    print(f"Final Response: {flow.state.response}")

def test_spending_flow():
    print("\n--- Testing Spending Flow ---")
    flow = BankingFlow()
    flow.state.account_number = "ACC123456"
    flow.state.query = "Based on my history, how much will I spend next month?"
    flow.kickoff()
    print(f"Final Response: {flow.state.response}")

if __name__ == "__main__":
    # Ensure some data exists for testing if needed
    # (In a real test we might want to seed the DB, 
    # but here we'll see how the agents handle existing or lack of data)
    
    test_investment_flow()
    test_spending_flow()
