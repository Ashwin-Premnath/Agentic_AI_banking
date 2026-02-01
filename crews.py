import os
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from crewai.tools import BaseTool
from crewai_tools import OCRTool, SerperDevTool, FileReadTool, DirectoryReadTool, FileWriterTool
load_dotenv()

# We use the 'openai/' prefix for reliability with Custom endpoints in LiteLLM (used by CrewAI)
# However, for this POC, we'll keep the nvidia_nim prefix if it works, or fallback to openai/
# Let's use openai/ to be safe against the 404s we saw earlier.
standard_llm = LLM(
    model="openai/meta/llama-3.1-70b-instruct",
    api_key=os.getenv("NVIDIA_API_KEY"),
    base_url="https://integrate.api.nvidia.com/v1",
    temperature=0.0
)

vision_llm = LLM(
    model="openai/nvidia/nemotron-nano-12b-v2-vl",
    api_key=os.getenv("NVIDIA_API_KEY"),
    base_url="https://integrate.api.nvidia.com/v1",
    temperature=0.0
)

serper_tool = SerperDevTool()

class NL2SQLTool(BaseTool):
    name: str = "NL2SQL Tool"
    description: str = (
        "Use this tool to interact with the bank's SQLite database. "
        "YOU MUST PROVIDE A VALID SQL QUERY AS THE INPUT. "
        "The tool will execute the SQL and return the results as a list of dictionaries. "
        "If the query is correctly formed but returns no data, it means the database is empty for that criteria. "
        "Tables available: 'customers' (id, name, email, account_number, balance), "
        "'transactions' (id, account_number, receiver_account_number, transaction_type, mode_of_payment, amount, timestamp), "
        "'investments' (id, account_number, asset_name, asset_type, invested_amount, current_value, timestamp). "
        "Relationships: All tables link via 'account_number'."
    )
    db_path: str = "bank_system_v3.db"

    def _run(self, query: str) -> str:
        import sqlite3
        import os
        try:
            sql = query.strip()
            sql = sql.replace("```sql", "").replace("```", "").replace("`", "").strip()
            
            # Defensive check for account numbers in queries - ensure they are treated as strings if needed
            # but SQLite is usually fine with either. 
            
            if not os.path.exists(self.db_path):
                return "Error: Database file 'bank_system_v3.db' not found in current directory."

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            
            # Check if it was a SELECT query or a modification query
            if cursor.description:
                rows = cursor.fetchall()
                header = [description[0] for description in cursor.description]
                conn.close()
                if not rows: 
                    return "NO_RECORDS_FOUND"
                return str([dict(zip(header, row)) for row in rows])
            else:
                # It was an UPDATE, INSERT, or DELETE
                affected = cursor.rowcount
                conn.close()
                return f"SUCCESS: {affected} rows affected."
        except Exception as e:
            return f"SQL Error: {str(e)}. Please correct your syntax."

def get_sql_tool(db_path):
    return NL2SQLTool(db_path=db_path)

class BankingCrews:
    def __init__(self, account_number=None):
        self.account_number = account_number
        self.db_path = "bank_system_v3.db"
        self.user_dir = f"user_data/{account_number}" if account_number else "user_data"
        self.uploads_dir = f"{self.user_dir}/uploads"
        
    def manager_crew(self):
        agent = Agent(
            role="Chief Banking Operations Officer",
            backstory="Central brain of the bank. Expert at routing user queries to the correct specialized crew.",
            goal="Orchestrate user requests by delegating to the perfect specialized banking crew.",
            llm=standard_llm,
            verbose=True
        )
        task = Task(
            description="Analyze the query: '{query}'. Context: Account={account_number}. "
                        "Identify the presiding department: "
                        "onboarding (new user registration), "
                        "account_query (financial balance, summary, transaction history, total wealth), "
                        "kyc_process (identity document verification), "
                        "market_analysis (stock prices, external rates), "
                        "interest_calc (savings/loan projections), "
                        "doc_mgmt (listing uploaded files), "
                        "policy_query (bank terms and conditions), "
                        "fd_form (creating fixed deposits), "
                        "investment_track (buying or tracking assets), "
                        "spending_forecast (predicting future expenses), "
                        "account_management (personal profile, name, email, updates, 'who am I' queries). "
                        "Return ONLY the lowercase keyword.",
            expected_output="A single lowercase keyword matching the department name.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def kyc_extraction_crew(self):
        agent = Agent(
            role="KYC Data Extractor",
            backstory="Senior banking auditor specializing in vision-based document transcription and verification.",
            goal="Extract and transcribe identity information from images/PDFs with high precision.",
            llm=vision_llm,
            verbose=True
        )
        task = Task(
            description="1. Vision analysis: Extract visible text from '{file_path}'. 2. Extraction: Name, ID, Expiry, Address. 3. Format as Markdown table.",
            expected_output="A Markdown table containing Name, ID Number, Expiry, and Address.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def kyc_storage_crew(self):
        agent = Agent(
            role="Data Security Officer",
            backstory="Responsible for banking data integrity and local storage security.",
            goal="Securely store verified KYC data into the user's isolated directory.",
            llm=standard_llm,
            verbose=True
        )
        task = Task(
            description="Save the following JSON data: '{pending_data}' to the path: '{processed_path}'.",
            expected_output="Confirmation of safe storage.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def account_crew(self):
        sql_tool = get_sql_tool(self.db_path)
        agent = Agent(
            role="Account Details Formatter",
            backstory="""You are a banking assistant specializing in data formatting. 
            You take raw SQL results and turn them into clean, human-readable Markdown tables. 
            You NEVER show raw data like '[]' or 'None'. 
            You ALWAYS use tables for balances and transactions.""",
            goal="Format the SQL results for {account_number} into the required Markdown structure.",
            llm=standard_llm,
            tools=[sql_tool],
            verbose=True,
            allow_delegation=False
        )
        task = Task(
            description="""
            1. Query the 'customers' table for the holder name and cash balance of {account_number}.
            2. Query the 'investments' table to sum the 'current_value' for {account_number}.
            3. Query the 'transactions' table for the 5 most recent activities related to {account_number}.
            4. Present the COMPREHENSIVE results using EXCLUSIVELY this format:

            ### Comprehensive Account Overview
            | Field | Value |
            | :--- | :--- |
            | Account Holder | **[Name]** |
            | Account Number | {account_number} |
            | Cash Balance | **$[Balance]** |
            | Total Investment Value | **$[Sum]** |

            ### Last Transaction Details
            [Table with ID, Type, Amount, Date of the single most recent transaction]

            ### Recent History
            | ID | Beneficiary | Type | Mode | Amount | Date |
            | :--- | :--- | :--- | :--- | :--- | :--- |
            [List last 5 transactions here. If none, write "| N/A | N/A | N/A | N/A | **$0.00** | N/A |"]

            > [!NOTE]
            > This report aggregates data from your profile, transaction logs, and investment portfolio.

            CRITICAL: Do not skip any sections. Always show the Account Holder name.
""",
            expected_output="A comprehensive Markdown report aggregating data from all relevant database tables.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def onboarding_data_crew(self):
        import random
        random_acc = "".join([str(random.randint(0, 9)) for _ in range(10)])
        agent = Agent(
            role="Onboarding Data Analyst",
            backstory="Registration specialist helping new customers open accounts.",
            goal="Collect and formulate new user data for account opening.",
            llm=standard_llm,
            verbose=True
        )
        task = Task(
            description=f"Process info: '{{query}}'. Suggest Account: {random_acc}. Ask for missing details or confirm summary.",
            expected_output="Request for missing data or a summary table with a confirmation question.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def onboarding_storage_crew(self):
        sql_tool = get_sql_tool(self.db_path)
        agent = Agent(
            role="Onboarding Data Security Officer",
            backstory="Specialist in database synchronization and new record creation.",
            goal="Securely finalize the registration process in the database.",
            llm=standard_llm,
            tools=[sql_tool],
            verbose=True
        )
        task = Task(
            description="INSERT the following verified data: '{verified_data}' into 'customers' table.",
            expected_output="Professional success confirmation.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def market_analysis_crew(self):
        agent = Agent(
            role="Financial Market Analyst",
            backstory="Expert in global financial markets and competitive rate analysis.",
            goal="Analyze and compare current bank deposit rates using the internet.",
            llm=standard_llm,
            tools=[serper_tool],
            verbose=True
        )
        task = Task(
            description="Search for market rates. Compare with query: '{query}'.",
            expected_output="Formatted Markdown report with market insights.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def interest_calculator_crew(self):
        sql_tool = get_sql_tool(self.db_path)
        agent = Agent(
            role="Financial Forecasting Specialist",
            backstory="""Expert at applying financial formulas to project future account earnings. 
            I NEVER invent a balance. If the tool returns nothing for {account_number}, I say 'Account not found'.""",
            goal="Calculate interest earnings and balance forecasts using account data for {account_number}.",
            llm=standard_llm,
            tools=[sql_tool],
            verbose=True
        )
        task = Task(
            description="""
            1. Fetch ACTUAL balance for {account_number}. 
            2. Calculate forecast based on '{query}'. 
            3. Present EXCLUSIVELY using this format:

            ### Interest Calculation Forecast
            | Period | Current Balance | Projected Interest | Total Forecast |
            | :--- | :--- | :--- | :--- |
            [Rows]
            
            > [!TIP]
            > [Insights based on real data]""",
            expected_output="Markdown response with a structured forecast table.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def doc_management_crew(self):
        file_tool = FileReadTool(encoding='utf-8')
        dir_tool = DirectoryReadTool(directory=self.uploads_dir)
        agent = Agent(
            role="Strict Digital Archive Assistant",
            backstory="""I am a literal digital archivist. I ONLY report files that physically exist in the uploads directory. 
            I NEVER invent, imagine, or hallucinate filenames (like 'file3.txt' or 'doc1.pdf'). 
            If the directory is empty, I MUST explicitly state that 'No documents found' or 'The directory is empty'.""",
            goal="Accurately list and describe files found in {uploads_dir} for account {account_number}.",
            llm=standard_llm,
            tools=[dir_tool, file_tool],
            verbose=True,
            allow_delegation=False
        )
        task = Task(
            description="""1. Use the DirectoryReadTool to check the contents of: {uploads_dir}.
            2. If the tool returns an empty list or 'No files found', respond that no documents are uploaded.
            3. If files exist, list them in a Markdown table with their names.
            4. DO NOT imagine any content or files that are not returned by the tool.""",
            expected_output="A Markdown table of ACTUAL documents found, or a clear message stating the folder is empty.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def policy_crew(self):
        file_tool = FileReadTool(file_path="policies/bank_policies.md", encoding='utf-8')
        agent = Agent(
            role="Bank Policy Specialist",
            backstory="Expert on internal bank regulations, fees, and procedures.",
            goal="Provide accurate information about bank policies and FAQs.",
            llm=standard_llm,
            tools=[file_tool],
            verbose=True
        )
        task = Task(
            description="Answer: '{query}' using the policy document.",
            expected_output="Accurate policy answer in Markdown.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def fd_crew(self):
        ocr_agent = Agent(
            role="Document OCR Specialist",
            backstory="Expert at reading complex banking forms via computer vision.",
            goal="Vision-based extraction of text and structure from forms.",
            llm=vision_llm,
            verbose=True
        )
        analyst_agent = Agent(
            role="Fixed Deposit Analyst",
            backstory="Expert at interpreting banking document constraints and mandatory fields.",
            goal="Verify FD application completeness based on OCR and context.",
            llm=standard_llm,
            tools=[FileReadTool(encoding='utf-8'), FileWriterTool(encoding='utf-8')],
            verbose=True
        )
        ocr_task = Task(
            description="Vision analysis on: '{file_path}'. Extract text and field markers.",
            expected_output="Raw text output from vision model.",
            agent=ocr_agent
        )
        analysis_task = Task(
            description="Analyze OCR for {user_context} and {accumulated_data}. check for missing markers '*'.",
            expected_output="Questions or Preview.",
            agent=analyst_agent,
            context=[ocr_task]
        )
        return Crew(agents=[ocr_agent, analyst_agent], tasks=[ocr_task, analysis_task], verbose=True)

    def investment_crew(self):
        sql_tool = get_sql_tool(self.db_path)
        tracker_agent = Agent(
            role="Investment Tracking Specialist",
            backstory="Detailed-oriented financial records keeper. Expert at tracking asset performance and updating investment databases.",
            goal="Accurately track and update investment details for {account_number}.",
            llm=standard_llm,
            tools=[sql_tool],
            verbose=True
        )
        forecaster_agent = Agent(
            role="Asset Growth Forecaster",
            backstory="Financial analyst specialized in predicting investment trends and asset growth based on historical data.",
            goal="Provide growth forecasts and insights for user's investments.",
            llm=standard_llm,
            tools=[serper_tool],
            verbose=True
        )
        tracking_task = Task(
            description="""1. Fetch current balance for {account_number}.
            2. Check if balance >= investment amount in '{query}'.
            3. If yes, UPDATE balance and INSERT investment.
            4. Report status using EXCLUSIVELY this format:

            ### Investment Transaction Status
            [Success/Failure Message]
            
            ### Current Investment Portfolio
            | Asset | Type | Invested | Current Value |
            | :--- | :--- | :--- | :--- |
            [Rows]""",
            expected_output="Markdown summary of investment status and holdings.",
            agent=tracker_agent
        )
        forecasting_task = Task(
            description="""Based on the holdings, provide a forecast using EXCLUSIVELY this format:
            
            ### Investment Growth Forecast
            | Asset | Predicted Growth | Confidence |
            | :--- | :--- | :--- |
            [Rows]
            
            > [!IMPORTANT]
            > [Market sentiment notes]""",
            expected_output="Markdown report with growth projections.",
            agent=forecaster_agent,
            context=[tracking_task]
        )
        return Crew(agents=[tracker_agent, forecaster_agent], tasks=[tracking_task, forecasting_task], verbose=True)

    def spending_forecast_crew(self):
        sql_tool = get_sql_tool(self.db_path)
        analyzer_agent = Agent(
            role="Spending Pattern Analyst",
            backstory="Expert at parsing transaction histories to identify recurring costs and spending habits.",
            goal="Analyze transaction history to understand spending patterns for {account_number}.",
            llm=standard_llm,
            tools=[sql_tool],
            verbose=True
        )
        predictor_agent = Agent(
            role="Expense Predictor",
            backstory="Data scientist focused on predictive modeling for personal finance and budgeting.",
            goal="Predict next month's spending based on historical transaction data.",
            llm=standard_llm,
            verbose=True
        )
        analysis_task = Task(
            description="""1. Fetch transactions for {account_number}. 
            2. Categorize spending into groups and present using EXCLUSIVELY this format:

            ### Spending Analysis Breakdown
            | Category | Amount | Percentage |
            | :--- | :--- | :--- |
            [Rows]""",
            expected_output="Categorized breakdown of spending in Markdown.",
            agent=analyzer_agent
        )
        prediction_task = Task(
            description="""Project expenses for next month using EXCLUSIVELY this format:
            
            ### Next Month Spending Projection
            | Metric | Forecasted Value |
            | :--- | :--- |
            | Projected Total | [Value] |
            | Major Category | [Category] |
            
            > [!TIP]
            > [Budgeting tips]""",
            expected_output="Markdown forecast of spending.",
            agent=predictor_agent,
            context=[analysis_task]
        )
        return Crew(agents=[analyzer_agent, predictor_agent], tasks=[analysis_task, prediction_task], verbose=True)

    def account_management_crew(self):
        sql_tool = get_sql_tool(self.db_path)
        agent = Agent(
            role="Account Profile Administrator",
            backstory="""You are a senior banking administrator with authority to update customer profile information. 
            You are meticuluous and ensure that every database update is accurate and reflects the user's intent. 
            You NEVER hallucinate data and ALWAYS verify that the update was successful.""",
            goal="Securely update customer profile details (name, email) for account {account_number}.",
            llm=standard_llm,
            tools=[sql_tool],
            verbose=True,
            allow_delegation=False
        )
        task = Task(
            description="""
            1. Parse the user's request: '{query}'.
            2. If it is a query for current profile details (e.g., "What is my name?"):
                a. FETCH and DISPLAY the current record.
            3. If it is an update request (e.g., "Change my email"):
                a. Check if the NEW value is provided in the query.
                b. If NO new value is found: 
                   - Inform the user clearly what is missing (e.g., "Please provide the new email address").
                   - Still display the CURRENT profile in the table below.
                c. If a new value IS found:
                   - UPDATE the database.
                   - FETCH the updated record.
            4. Present the result using EXCLUSIVELY this format:

            ### User Profile Management
            | Field | Value | Status |
            | :--- | :--- | :--- |
            | Account Holder | **[Name]** | [Current / Updated / Awaiting Info] |
            | Email Address | [Email] | [Current / Updated / Awaiting Info] |
            | Account Number | {account_number} | Verified |

            > [!NOTE]
            > Account data sync is performed in real-time with our core banking systems.

            DO NOT output raw SQL. If information is missing for an update, ask for it politely but keep the table.""",
            expected_output="A structured Markdown profile view, with updates applied or missing info requested.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)
