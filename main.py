import os
import json
import shutil
from datetime import datetime
from dotenv import load_dotenv
from crewai.flow.flow import Flow, start, listen, router, or_
from pydantic import BaseModel
from typing import Optional
from crews import BankingCrews

load_dotenv()

class BankingState(BaseModel):
    account_number: str = "GUEST"
    query: str = ""
    file_path: Optional[str] = None
    intent: str = ""
    response: str = ""
    user_dir: str = ""
    pending_kyc_data: Optional[str] = None
    awaiting_confirmation: bool = False
    pending_onboarding_data: Optional[str] = None
    onboarding_awaiting_confirmation: bool = False
    pending_fd_data: Optional[str] = None
    last_sql_query: Optional[str] = None
    last_db_result: Optional[str] = None
    db_operation_success: bool = False


class BankingFlow(Flow[BankingState]):

    @start()
    def initialize_session(self):
        print(f" Initializing session for: {self.state.account_number}")
        self.state.user_dir = f"user_data/{self.state.account_number}"
        directories = [
            f"{self.state.user_dir}/uploads",
            f"{self.state.user_dir}/queries",
            f"{self.state.user_dir}/responses",
            f"{self.state.user_dir}/processed",
            f"{self.state.user_dir}/FD",
            f"{self.state.user_dir}/investments"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
        if self.state.file_path and os.path.exists(self.state.file_path):
            filename = os.path.basename(self.state.file_path)
            new_path = f"{self.state.user_dir}/uploads/{filename}"
            shutil.copy(self.state.file_path, new_path)
            self.state.file_path = new_path
            print(f" File moved to: {new_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_log = {
            "timestamp": timestamp,
            "query": self.state.query,
            "file": self.state.file_path,
            "account_number": self.state.account_number
        }

        query_log_path = f"{self.state.user_dir}/queries/query_{timestamp}.json"
        with open(query_log_path, "w", encoding="utf-8") as f:
            json.dump(query_log, f, indent=2)
        print(f" Query logged to: {query_log_path}")

    @listen(initialize_session)
    def determine_intent(self):
        print("\n Chief Manager analyzing query...")
        crews = BankingCrews(self.state.account_number)
        result = crews.manager_crew().kickoff(inputs={
            "query": self.state.query,
            "account_number": self.state.account_number
        })
        self.state.intent = str(result).strip().lower().replace(".", "").replace("#", "").split()[0]
        print(f" Manager Decision: Route to '{self.state.intent}' department")

    @router(determine_intent)
    def route_request(self):
        return self.state.intent

    @listen("onboarding")
    def handle_onboarding(self):
        print("\n Processing Onboarding Request...")
        crews = BankingCrews(self.state.account_number)
        
        result = crews.onboarding_data_crew().kickoff(inputs={
            "query": self.state.query
        })
        
        # Check if we have complete data (indicated by table format)
        if "|" in str(result) and "Account Number" in str(result):
            self.state.pending_onboarding_data = str(result)
            self.state.onboarding_awaiting_confirmation = True
            self.state.response = (
                f"{result}\n\n"
                "**Is this information correct?** "
                "Please reply with 'Yes' or 'Correct' to create your account in the database."
            )
            print(" Complete data collected, awaiting user confirmation")
        else:
            self.state.response = str(result)
            print("⏳ Requesting additional information from user")

    @listen("onboarding_confirm")
    def handle_onboarding_confirmation(self):
        print("\n Confirming Onboarding & Creating Database Record...")
        crews = BankingCrews(self.state.account_number)
        
        result = crews.onboarding_storage_crew().kickoff(inputs={
            "verified_data": self.state.pending_onboarding_data
        })
        
        self.state.response = str(result)
        self.state.onboarding_awaiting_confirmation = False
        self.state.pending_onboarding_data = None
        self.state.db_operation_success = True
        print(" Account created successfully in database")

    @listen("onboarding_reject")
    def handle_onboarding_rejection(self):
        """Handle user rejection of onboarding data"""
        print("\n User rejected onboarding data")
        self.state.onboarding_awaiting_confirmation = False
        self.state.pending_onboarding_data = None
        self.state.response = (
            "Understood. I have cancelled the registration. "
            "Let me know if you'd like to try again or need anything else."
        )

    @listen("account_query")
    def handle_account_query(self):
        """Handle account information queries with database access"""
        print("\n Processing Account Query with Database Access...")
        crews = BankingCrews(self.state.account_number)
        
        result = crews.account_crew().kickoff(inputs={
            "query": self.state.query,
            "account_number": self.state.account_number
        })
        
        self.state.response = str(result)
        self.state.db_operation_success = True
        print(" Account information retrieved from database")

    @listen("kyc_process")
    def handle_kyc(self):
        """Handle KYC document processing"""
        print("\n Processing KYC Document...")
        
        if not self.state.file_path:
            self.state.response = "Please upload a document for KYC processing."
            print(" No file provided for KYC")
            return

        crews = BankingCrews(self.state.account_number)
        result = crews.kyc_extraction_crew().kickoff(inputs={
            "file_path": self.state.file_path
        })
        
        self.state.pending_kyc_data = str(result)
        self.state.awaiting_confirmation = True
        self.state.response = (
            f"I've extracted the following details:\n\n{result}\n\n"
            "**Is this information correct?** "
            "Please reply with 'Yes' or 'Correct' to proceed with storage."
        )
        print(" KYC data extracted, awaiting user confirmation")

    @listen("kyc_confirm")
    def handle_kyc_confirmation(self):
        """Confirm and store KYC data"""
        print("\n Storing Confirmed KYC Data...")
        crews = BankingCrews(self.state.account_number)
        
        processed_filename = f"kyc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        processed_path = f"{self.state.user_dir}/processed/{processed_filename}"
        
        result = crews.kyc_storage_crew().kickoff(inputs={
            "pending_data": self.state.pending_kyc_data,
            "processed_path": processed_path
        })
        
        self.state.response = f"Thank you! {result}"
        self.state.awaiting_confirmation = False
        self.state.pending_kyc_data = None
        print(f" KYC data stored at: {processed_path}")

    @listen("kyc_reject")
    def handle_kyc_rejection(self):
        """Handle user rejection of KYC data"""
        print("\n User rejected KYC data")
        self.state.awaiting_confirmation = False
        self.state.pending_kyc_data = None
        self.state.response = (
            "Understood. I have cancelled the storage processing. "
            "You can upload a new document or ask me something else."
        )

    @listen("market_analysis")
    def handle_market_analysis(self):
        """Handle market analysis queries"""
        print("\n Processing Market Analysis Request...")
        crews = BankingCrews(self.state.account_number)
        
        result = crews.market_analysis_crew().kickoff(inputs={
            "query": self.state.query
        })
        
        self.state.response = str(result)
        print(" Market analysis completed")

    @listen("interest_calc")
    def handle_interest_calc(self):
        """Handle interest calculation with optional database storage"""
        print("\n Calculating Interest & Returns...")
        crews = BankingCrews(self.state.account_number)
        
        result = crews.interest_calculator_crew().kickoff(inputs={
            "query": self.state.query,
            "account_number": self.state.account_number
        })
        
        self.state.response = str(result)
        print(" Interest calculation completed")

    @listen("doc_mgmt")
    def handle_doc_mgmt(self):
        """Handle document management queries"""
        print("\n Managing Documents...")
        crews = BankingCrews(self.state.account_number)
        
        result = crews.doc_management_crew().kickoff(inputs={
            "uploads_dir": f"{self.state.user_dir}/uploads"
        })
        self.state.response = str(result)
        print(" Document listing completed")

    @listen("policy_query")
    def handle_policy(self):
        """Handle banking policy queries"""
        print("\n Retrieving Policy Information...")
        crews = BankingCrews(self.state.account_number)
        
        result = crews.policy_crew().kickoff(inputs={
            "query": self.state.query
        })
        
        self.state.response = str(result)
        print(" Policy information provided")

    @listen("fd_form")
    def handle_fd_form(self):
        """Handle Fixed Deposit form processing with database integration"""
        print("\n Processing Fixed Deposit Application...")
        
        if not self.state.file_path:
            self.state.response = (
                "Please upload the FD form (image or PDF) to start the application."
            )
            print(" No FD form file provided")
            return
            
        crews = BankingCrews(self.state.account_number)
        
        # Initialize pending data if first run
        if not self.state.pending_fd_data:
            self.state.pending_fd_data = "No data collected yet."
            
        result = crews.fd_crew().kickoff(inputs={
            "file_path": self.state.file_path,
            "user_context": self.state.query,
            "accumulated_data": self.state.pending_fd_data,
            "account_number": self.state.account_number
        })
        
        self.state.response = str(result)
        
        # Store the latest state for conversational continuity
        if "preview" in str(result).lower() or "|" in str(result):
            self.state.pending_fd_data = str(result)
            print(" FD data collected, preview generated")
        else:
            print("⏳ Gathering additional FD information")

    @listen("investment_track")
    def handle_investment(self):
        """Handle investment tracking and portfolio management with database"""
        print("\n Processing Investment Request...")
        crews = BankingCrews(self.state.account_number)
        
        result = crews.investment_crew().kickoff(inputs={
            "query": self.state.query,
            "account_number": self.state.account_number
        })
        
        self.state.response = str(result)
        self.state.db_operation_success = True
        print(" Investment portfolio retrieved/updated")

    @listen("spending_forecast")
    def handle_spending_forecast(self):
        """Handle spending analysis and forecasting with database queries"""
        print("\n Analyzing Spending Patterns...")
        crews = BankingCrews(self.state.account_number)
        
        result = crews.spending_forecast_crew().kickoff(inputs={
            "account_number": self.state.account_number
        })
        
        self.state.response = str(result)
        self.state.db_operation_success = True
        print(" Spending analysis completed")

    @listen("account_management")
    def handle_account_management(self):
        """Handle account management and profile updates with database"""
        print("\n Managing Account Profile...")
        crews = BankingCrews(self.state.account_number)
        
        result = crews.account_management_crew().kickoff(inputs={
            "query": self.state.query,
            "account_number": self.state.account_number
        })
        
        self.state.response = str(result)
        self.state.db_operation_success = True
        print(" Account management operation completed")

    @listen("general")
    def handle_general(self):
        """Handle general queries"""
        print("\n Handling General Query...")
        self.state.response = (
            "I'm here to help with banking services. You can ask about:\n\n"
            "- Account balance and transactions\n"
            "- New account registration\n"
            "- KYC document processing\n"
            "- Investment tracking and analysis\n"
            "- Fixed deposits\n"
            "- Spending forecasts\n"
            "- Interest calculations\n"
            "- Market analysis\n"
            "- Banking policies and rates\n\n"
            "How can I assist you today?"
        )

    @listen(or_(
        handle_onboarding, 
        handle_account_query, 
        handle_kyc, 
        handle_market_analysis, 
        handle_interest_calc, 
        handle_doc_mgmt, 
        handle_policy, 
        handle_fd_form, 
        handle_investment, 
        handle_spending_forecast,
        handle_account_management,
        handle_kyc_confirmation, 
        handle_kyc_rejection, 
        handle_onboarding_confirmation, 
        handle_onboarding_rejection, 
        handle_general
    ))
    def log_response(self):
        """Log the final response with metadata"""
        print("\n Logging Response...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response_log = {
            "timestamp": timestamp,
            "account_number": self.state.account_number,
            "intent": self.state.intent,
            "query": self.state.query,
            "response": self.state.response,
            "db_operation_success": self.state.db_operation_success,
            "file_processed": self.state.file_path if self.state.file_path else None
        }
        
        response_log_path = f"{self.state.user_dir}/responses/resp_{timestamp}.json"
        with open(response_log_path, "w", encoding="utf-8") as f:
            json.dump(response_log, f, indent=2, ensure_ascii=False)
        
        print(f" Response logged to: {response_log_path}")
        print("\n" + "="*60)
        print(" Session Complete")
        print("="*60)


def run_banking_flow(account_number: str, query: str, file_path: Optional[str] = None):
    """
    Convenience function to run the banking flow
    
    Args:
        account_number: Customer account number
        query: User's query or request
        file_path: Optional path to uploaded file
        
    Returns:
        The final response from the flow
    """
    flow = BankingFlow()
    flow.state.account_number = account_number
    flow.state.query = query
    if file_path:
        flow.state.file_path = file_path
    
    flow.kickoff()
    return flow.state.response


if __name__ == "__main__":
    # Example usage scenarios
    
    print("="*60)
    print(" Banking Flow System - Enhanced with Database Access")
    print("="*60)
    
    # Example 1: Account Balance Query (Database Read)
    print("\n\n Example 1: Account Balance Query")
    print("-" * 60)
    response = run_banking_flow(
        account_number="ACC123456",
        query="What is my current balance?"
    )
    print(f"\n Response:\n{response}")
    
    # Example 2: Investment Tracking (Database Read/Write)
    print("\n\n Example 2: Buy Investment")
    print("-" * 60)
    response = run_banking_flow(
        account_number="ACC123456",
        query="I want to buy Apple stock worth $5000"
    )
    print(f"\n Response:\n{response}")
    
    # Example 3: Profile Update (Database Update)
    print("\n\n Example 3: Update Email")
    print("-" * 60)
    response = run_banking_flow(
        account_number="ACC123456",
        query="Update my email to john.doe@newmail.com"
    )
    print(f"\n Response:\n{response}")
    
    # Example 4: Transaction History (Database Query)
    print("\n\n Example 4: Transaction History")
    print("-" * 60)
    response = run_banking_flow(
        account_number="ACC123456",
        query="Show me my recent transactions"
    )
    print(f"\n Response:\n{response}")
    
    print("\n\n" + "="*60)
    print(" All Examples Completed")
    print("="*60)