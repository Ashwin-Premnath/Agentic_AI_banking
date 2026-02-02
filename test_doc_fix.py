import os
from crews import BankingCrews

def test_doc_management_hallucination():
    # Setup: Use a test account
    test_account = "TEST_EMPTY_FOLDER"
    crews = BankingCrews(test_account)
    
    # Ensure the directory exists but is empty
    os.makedirs(crews.uploads_dir, exist_ok=True)
    for f in os.listdir(crews.uploads_dir):
        os.remove(os.path.join(crews.uploads_dir, f))
    
    print(f"Testing document management for empty folder: {crews.uploads_dir}")
    
    # Run the crew
    crew = crews.doc_management_crew()
    result = crew.kickoff(inputs={"uploads_dir": crews.uploads_dir, "account_number": test_account})
    
    print("\n--- Agent Response ---")
    print(result)
    print("----------------------")
    
    # Check for hallucinations
    hallucination_indicators = ["file3.txt", "doc1.pdf", "sample.txt"]
    hallucinated = any(indicator in str(result).lower() for indicator in hallucination_indicators)
    
    if hallucinated:
        print("FAIL: Agent is still hallucinating generic file names.")
    elif "no documents" in str(result).lower() or "empty" in str(result).lower():
        print("PASS: Agent correctly identified the empty folder.")
    else:
        print("UNSURE: Check response manually.")

if __name__ == "__main__":
    test_doc_management_hallucination()
