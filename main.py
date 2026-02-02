import os
import json
import shutil
from datetime import datetime
from dotenv import load_dotenv
from crewai.flow.flow import Flow, start, listen, router, or_
from pydantic import BaseModel
from crews import BankingCrews

load_dotenv()

from typing import Optional

class BankingState(BaseModel):
    account_number: str = "GUEST"
    query: str = ""
    file_path: Optional[str] = None
    intent: str = ""
    response: str = ""
    user_dir: str = ""
    pending_kyc_data: Optional[str] = None
    pending_onboarding_data: Optional[str] = None
    awaiting_confirmation: bool = False
    onboarding_awaiting_confirmation: bool = False
    pending_fd_data: Optional[str] = None

class BankingFlow(Flow[BankingState]):

    @start()
    def initialize_session(self):
        print(f"Initializing session for: {self.state.account_number}")
        
        # Setup user directory structure
        self.state.user_dir = f"user_data/{self.state.account_number}"
        os.makedirs(f"{self.state.user_dir}/uploads", exist_ok=True)
        os.makedirs(f"{self.state.user_dir}/queries", exist_ok=True)
        os.makedirs(f"{self.state.user_dir}/responses", exist_ok=True)
        os.makedirs(f"{self.state.user_dir}/processed", exist_ok=True)
        os.makedirs(f"{self.state.user_dir}/FD", exist_ok=True)
        
        # Handle file upload move (if any)
        if self.state.file_path and os.path.exists(self.state.file_path):
            filename = os.path.basename(self.state.file_path)
            new_path = f"{self.state.user_dir}/uploads/{filename}"
            shutil.copy(self.state.file_path, new_path)
            self.state.file_path = new_path
            print(f"File moved to: {new_path}")

        # Log query
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_log = {
            "timestamp": timestamp,
            "query": self.state.query,
            "file": self.state.file_path
        }
        with open(f"{self.state.user_dir}/queries/query_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(query_log, f)

    @listen(initialize_session)
    def determine_intent(self):
        print("Chief Manager is analyzing query...")
        crews = BankingCrews(self.state.account_number)
        result = crews.manager_crew().kickoff(inputs={
            "query": self.state.query,
            "account_number": self.state.account_number
        })
        
        # Manager returns the route name directly (e.g., "onboarding", "kyc_process")
        self.state.intent = str(result).strip().lower().replace(".", "").replace("#", "").split()[0]
        print(f"Manager Order: {self.state.intent}")

    @router(determine_intent)
    def route_request(self):
        # The manager's intent now matches the listener strings exactly
        return self.state.intent

    @listen("onboarding")
    def handle_onboarding(self):
        print("Handling Onboarding Data Collection...")
        crews = BankingCrews(self.state.account_number)
        result = crews.onboarding_data_crew().kickoff(inputs={"query": self.state.query})
        
        # If the result contains a Markdown table, assume we are ready for confirmation
        if "|" in str(result) and "Account Number" in str(result):
            self.state.pending_onboarding_data = str(result)
            self.state.onboarding_awaiting_confirmation = True
            self.state.response = f"{result}\n\n**Is this information correct?** Please reply with 'Yes' or 'Correct' to create your account."
        else:
            self.state.response = str(result)

    @listen("onboarding_confirm")
    def handle_onboarding_confirmation(self):
        print("Handling Onboarding Confirmation...")
        crews = BankingCrews(self.state.account_number)
        result = crews.onboarding_storage_crew().kickoff(inputs={
            "verified_data": self.state.pending_onboarding_data
        })
        self.state.response = str(result)
        self.state.onboarding_awaiting_confirmation = False
        self.state.pending_onboarding_data = None

    @listen("onboarding_reject")
    def handle_onboarding_rejection(self):
        print("Handling Onboarding Rejection...")
        self.state.onboarding_awaiting_confirmation = False
        self.state.pending_onboarding_data = None
        self.state.response = "Understood. I have cancelled the registration. Let me know if you'd like to try again or need anything else."

    @listen("account_query")
    def handle_account_query(self):
        print("Handling Account Query...")
        crews = BankingCrews(self.state.account_number)
        result = crews.account_crew().kickoff(inputs={
            "query": self.state.query,
            "account_number": self.state.account_number
        })
        self.state.response = str(result)

    @listen("kyc_process")
    def handle_kyc(self):
        print("Handling KYC Process...")
        if not self.state.file_path:
            self.state.response = "Please upload a document for KYC processing."
            return

        crews = BankingCrews(self.state.account_number)
        result = crews.kyc_extraction_crew().kickoff(inputs={"file_path": self.state.file_path})
        
        self.state.pending_kyc_data = str(result)
        self.state.awaiting_confirmation = True
        self.state.response = f"I've extracted the following details:\n\n{result}\n\n**Is this information correct?** Please reply with 'Yes' or 'Correct' to proceed with storage."

    @listen("kyc_confirm")
    def handle_kyc_confirmation(self):
        print("Handling KYC Confirmation...")
        crews = BankingCrews(self.state.account_number)
        processed_filename = f"kyc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        processed_path = f"{self.state.user_dir}/processed/{processed_filename}"
        
        # In a real app, you'd parse self.state.pending_kyc_data (Markdown) into JSON
        # For this POC, we'll store the verified summary as a confirmed record.
        result = crews.kyc_storage_crew().kickoff(inputs={
            "pending_data": self.state.pending_kyc_data,
            "processed_path": processed_path
        })
        
        self.state.response = f"Thank you! {result}"
        self.state.awaiting_confirmation = False
        self.state.pending_kyc_data = None

    @listen("kyc_reject")
    def handle_kyc_rejection(self):
        print("Handling KYC Rejection/Cancellation...")
        self.state.awaiting_confirmation = False
        self.state.pending_kyc_data = None
        self.state.response = "Understood. I have cancelled the storage processing. You can upload a new document or ask me something else."

    @listen("market_analysis")
    def handle_market_analysis(self):
        print("Handling Market Analysis...")
        crews = BankingCrews(self.state.account_number)
        result = crews.market_analysis_crew().kickoff(inputs={"query": self.state.query})
        self.state.response = str(result)

    @listen("interest_calc")
    def handle_interest_calc(self):
        print("Handling Interest Calculation & Forecasting...")
        crews = BankingCrews(self.state.account_number)
        result = crews.interest_calculator_crew().kickoff(inputs={
            "query": self.state.query,
            "account_number": self.state.account_number
        })
        self.state.response = str(result)

    @listen("doc_mgmt")
    def handle_doc_mgmt(self):
        print("Handling Document Management...")
        crews = BankingCrews(self.state.account_number)
        result = crews.doc_management_crew().kickoff(inputs={
            "uploads_dir": f"user_data/{self.state.account_number}/uploads"
        })
        self.state.response = str(result)

    @listen("policy_query")
    def handle_policy(self):
        print("Handling Policy Query...")
        crews = BankingCrews(self.state.account_number)
        result = crews.policy_crew().kickoff(inputs={"query": self.state.query})
        self.state.response = str(result)

    @listen("fd_form")
    def handle_fd_form(self):
        print("Handling FD Form Processing...")
        if not self.state.file_path:
            self.state.response = "Please upload the FD form (image or PDF) to start the application."
            return
            
        crews = BankingCrews(self.state.account_number)
        
        # We maintain a conversational context. 
        # On first run, it's just the query. 
        # On subsequent runs, we provide the previously collected data.
        if not self.state.pending_fd_data:
            self.state.pending_fd_data = "No data collected yet."
            
        result = crews.fd_crew().kickoff(inputs={
            "file_path": self.state.file_path,
            "user_context": self.state.query,
            "accumulated_data": self.state.pending_fd_data
        })
        
        # The agent's result might be questions OR a summary.
        # We store the latest summary/state in pending_fd_data to keep the agent updated.
        self.state.response = str(result)
        
        # If the result looks like a structured summary or preview, we keep it as our base
        if "preview" in str(result).lower() or "|" in str(result):
            self.state.pending_fd_data = str(result)

    @listen("investment_track")
    def handle_investment(self):
        print("Handling Investment Tracking & Forecasting...")
        crews = BankingCrews(self.state.account_number)
        result = crews.investment_crew().kickoff(inputs={
            "query": self.state.query,
            "account_number": self.state.account_number
        })
        self.state.response = str(result)

    @listen("spending_forecast")
    def handle_spending_forecast(self):
        print("Handling Spending Analysis & Forecasting...")
        crews = BankingCrews(self.state.account_number)
        result = crews.spending_forecast_crew().kickoff(inputs={
            "account_number": self.state.account_number
        })
        self.state.response = str(result)

    @listen("account_management")
    def handle_account_management(self):
        print("Handling Account Management / Profile Updates...")
        crews = BankingCrews(self.state.account_number)
        result = crews.account_management_crew().kickoff(inputs={
            "query": self.state.query,
            "account_number": self.state.account_number
        })
        self.state.response = str(result)

    @listen("general")
    def handle_general(self):
        self.state.response = "I'm here to help with banking. You can ask about accounts, KYC, interest rates, or onboarding."

    @listen(or_(handle_onboarding, handle_account_query, handle_kyc, 
               handle_market_analysis, handle_interest_calc, handle_doc_mgmt, 
               handle_policy, handle_fd_form, handle_investment, handle_spending_forecast,
               handle_account_management,
               handle_kyc_confirmation, handle_kyc_rejection, 
               handle_onboarding_confirmation, handle_onboarding_rejection, handle_general))
    def log_response(self):
        print("Logging response...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response_log = {
            "timestamp": timestamp,
            "intent": self.state.intent,
            "response": self.state.response
        }
        with open(f"{self.state.user_dir}/responses/resp_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(response_log, f)
        print("Session Complete.")

if __name__ == "__main__":
    # Example manual run
    flow = BankingFlow()
    flow.state.account_number = "ACC123456"
    flow.state.query = "What is my current balance?"
    flow.kickoff()
    print(f"Final Response: {flow.state.response}")
