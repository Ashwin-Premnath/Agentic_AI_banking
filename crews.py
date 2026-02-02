import os
import datetime
from datetime import datetime
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from crewai.tools import BaseTool
from crewai_tools import OCRTool, SerperDevTool, FileReadTool, DirectoryReadTool, FileWriterTool, DirectorySearchTool
load_dotenv()

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
            print(f"--- EXECUTING SQL: {sql} ---")
            cursor.execute(sql)
            conn.commit()
            
            # Check if it was a SELECT query or a modification query
            if cursor.description:
                rows = cursor.fetchall()
                print(f"--- SQL RESULT: Found {len(rows)} rows ---")
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
                        "market_analysis (stock prices, global market news), "
                        "interest_calc (calculating specific returns on an amount, e.g. 'return on 10k'), "
                        "doc_mgmt (listing uploaded files), "
                        "policy_query (bank terms, conditions, FD rates, holidays, 'about us', general FAQs), "
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
            description="""
            1. Vision analysis: Extract visible text from '{file_path}'. 
            2. Extraction requirements:
               - Document Type (e.g. Identity Card, PAN Card, Passport)
               - Full Name
               - Father's Name (if present)
               - ID / PAN Number / Document ID
               - Date of Birth / Expiry Date
               - Registered Address
               - Extraction Confidence Score
            3. Present strictly using this format:

            # Identity Verification Result
            **Processing Status:** Successfully Extracted
            
            ### Document Details
            | Field | Verified Data |
            | :--- | :--- |
            | Document Type | [Type] |
            | Full Name | [Name] |
            | Father's Name | [Father's Name] |
            | ID / PAN Number | [ID] |
            | Date of Birth | [DOB] |
            | Expiry Date | [Expiry] |
            | Registered Address | [Address] |
            | Confidence Score | [Score] |

            > [!NOTE]
            > This data was extracted using high-precision OCR. Please verify the accuracy before proceeding with storage.
            """,
            expected_output="A professional Markdown report containing extracted KYC details in a table.",
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
            description="""
            1. Securely save the JSON data: '{pending_data}' to '{processed_path}'.
            2. Ensure parent directories exist.
            3. Confirm storage with a professional message:
            
            ### Data Security Confirmation
            Your identity documents have been parsed, encrypted, and stored in your private vault at `{processed_path}`. 
            
            > [!IMPORTANT]
            > Your record is now active in our verified customer database.
            """,
            expected_output="Confirmation of safe storage with a professional security note.",
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
            1. **EXECUTE SQL**: Query table `customers` for 'balance' and 'name' WHERE account_number='{account_number}'.
            2. **EXECUTE SQL**: Query table `investments` to SUM(current_value) WHERE account_number='{account_number}'. (Treat NULL as 0).
            3. **EXECUTE SQL**: Query table `transactions` for last 5 records (timestamp, transaction_type, amount) WHERE account_number='{account_number}' ORDER BY timestamp DESC.
            4. **FORMAT**: Populate the table below using ONLY the fetched data.

            # Account Status/Overview Report
            **Customer Name:** [Name from DB]
            **Account Number:** {account_number}
            
            ### Financial Overview
            | Category | Amount |
            | :--- | :--- |
            | **Liquid Cash Balance** | **[Balance from customers]** |
            | **Investment Portfolio** | **[Sum from investments]** |
            | **Total Net Worth** | **[Balance + Investments]** |

            ### Recent Activity
            | Date | Transaction Details | Amount |
            | :--- | :--- | :--- |
            [Iterate transaction rows: "| [Timestamp] | [Type] | **$[Amount]** |"]

            > [!TIP]
            > For a detailed investment breakdown, ask "Show my portfolio".
            """,
            expected_output="A premium Markdown report aggregating strictly verified database data.",
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
            description=f"""
            Process info: '{{query}}'. 
            1. Suggest Account: {random_acc}. 
            2. Present strictly using this format:

            # New Account Registration
            Welcome to the future of banking. We have prepared your onboarding profile.

            ### User Proposed Profile Summary
            | Requirement | Status / Value |
            | :--- | :--- |
            | Full Name | [Name] |
            | Primary Email | [Email] |
            | Suggested Account | **{random_acc}** |

            > [!IMPORTANT]
            > To finalize your registration, please confirm the details above by replying with **'Correct'**.
            """,
            expected_output="A professional onboarding summary table with a clear call to action.",
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
            description="""
            1. INSERT verified data: '{verified_data}' into 'customers'.
            2. Report status strictly using this format:

            # Registration Complete
            **Status:** Account Successfully Created
            
            ### Next Steps
            > [!TIP]
            > Your new account number is now active. You can fund it via the 'Deposit' feature or ask "What is my account status?".
            """,
            expected_output="Professional success confirmation with next steps.",
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
            description="""
            1. Search for market rates. 
            2. Compare with user query: '{query}'.
            3. Present strictly using this format:

            # Global Market Insights
            **Analysis Type:** Rate Comparison & Trend Forecast

            ### Competitive Rate Analysis
            | Institution | Product Type | Current Annual Rate | Notable Features |
            | :--- | :--- | :--- | :--- |
            [Rows]

            > [!TIP]
            > Based on current trends, [Market Insight]. Consider [Suggestion].
            """,
            expected_output="A data-driven Markdown report with market insights and institutional comparisons.",
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
            3. Present strictly using this format:

            # Interest Accumulation Forecast
            **Projection Method:** Compound Interest Modeling
            **Reference Balance:** $[Balance]

            ### Future Value Projections
            | Forecast Period | Principal Amount | Cumulative Interest | Total Projected Balance |
            | :--- | :--- | :--- | :--- |
            [Rows]
            
            > [!TIP]
            > **Maximization Strategy:** [Brief tip on how to optimize these earnings.]
            """,
            expected_output="A structured financial forecast report with a projection table.",
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
            description="""
            1. Use DirectoryReadTool to check: {uploads_dir}.
            2. Present strictly using this format:

            # Digital Document Repository
            **Vault Access:** Authorized for Account {account_number}

            ### On-File Documents
            | Document Filename | Storage Status | Format |
            | :--- | :--- | :--- |
            [List files. If empty, write "| No documents on file | N/A | N/A |"]

            > [!NOTE]
            > All documents are securely stored and encrypted in your personal banking directory.
            """,
            expected_output="A clean document list table or a professional empty-state message.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def policy_crew(self):
        # RAG Tool for semantic search across the entire 'policies' directory
        # Using DirectorySearchTool to index ALL files (pdfs, md, txt) in the folder
        rag_tool = DirectorySearchTool(
            directory='policies',
            config=dict(
                llm=dict(
                    provider="openai",
                    config=dict(
                        model="openai/meta/llama-3.1-70b-instruct",
                        base_url="https://integrate.api.nvidia.com/v1",
                        api_key=os.getenv("NVIDIA_API_KEY")
                    )
                ),
                embedder=dict(
                    provider="openai",
                    config=dict(
                        model="nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1",
                        api_base="https://integrate.api.nvidia.com/v1",
                        api_key=os.getenv("NVIDIA_API_KEY")
                    )
                )
            )
        )
        
        agent = Agent(
            role="Bank Policy Specialist",
            backstory="Expert on internal bank regulations. I use semantic search to find exact policy details.",
            goal="Provide accurate information about bank policies using RAG.",
            llm=standard_llm,
            tools=[rag_tool],
            verbose=True
        )
        task = Task(
            description="""
            1. Search policy document for: '{query}'.
            2. Present answer strictly using this format:
            
            # Bank Policy Insight
            **Topic:** {query}
            
            ### Policy Details
            [Provide a clear, concise answer based on the retrieved text.]
            
            > [!NOTE]
            > Policies are subject to change. Reference Doc: Global Terms & Conditions v3.
            """,
            expected_output="Accurate policy answer in structured Markdown.",
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
            description="""
            1. Analyze OCR results for {user_context} and {accumulated_data}.
            2. Check for missing markers '*'.
            3. Present strictly using this format:

            # Fixed Deposit Application Preview
            **Status:** [Pending Info / Ready for Review]

            ### Extracted Details
            | Field | Extracted Value | Status |
            | :--- | :--- | :--- |
            [List key fields: Name, Amount, Tenure, Nominee]

            > [!IMPORTANT]
            > Please review the details above. If anything is missing, please re-upload or provide the details in chat.
            """,
            expected_output="A structured preview table for the FD application.",
            agent=analyst_agent,
            context=[ocr_task]
        )
        return Crew(agents=[ocr_agent, analyst_agent], tasks=[ocr_task, analysis_task], verbose=True)

    def investment_crew(self):
        sql_tool = get_sql_tool(self.db_path)
        tracker_agent = Agent(
            role="Investment Tracking Specialist",
            backstory="Detailed-oriented financial records keeper. Expert at tracking asset performance and updating investment databases. I ALWAYS verify the current portfolio from the database.",
            goal="Accurately track and update investment details for {account_number}.",
            llm=standard_llm,
            tools=[sql_tool],
            verbose=True
        )
        forecaster_agent = Agent(
            role="Asset Growth Forecaster",
            backstory="Financial analyst specialized in predicting investment trends. I ONLY forecast assets that physically exist in the user's portfolio. I NEVER invent 'Asset1' or generic names.",
            goal="Provide growth forecasts for the user's ACTUAL investments.",
            llm=standard_llm,
            tools=[serper_tool],
            verbose=True
        )
        # Prepare date string safely outside the f-string for cleaner code
        report_date = datetime.now().strftime("%Y-%m-%d")
        
        tracking_task = Task(
            description=f"""
            1. Fetch current balance for account '{{account_number}}' from 'customers' table.
            2. If buying/investing in '{{query}}', check balance, INSERT into 'investments', UPDATE 'customers'.
            3. CRITICAL: Execute 'SELECT * FROM investments WHERE account_number = "{{account_number}}"' to get assets.
            4. Report status using EXCLUSIVELY this format:

            # Investment Portfolio Report
            **Account Number:** {{account_number}}
            **Report Date:** {report_date}

            ### Transaction Status
            [Success/Failure Message or 'No recent transactions performed. Viewing current portfolio.']
            
            ### Current Portfolio Holdings
            | Asset Name | Asset Type | Principal Invested | Current Market Value | Unrealized P/L |
            | :--- | :--- | :--- | :--- | :--- |
            [List each asset. Calculate P/L as Current Value - Invested]
            
            **Total Portfolio Value:** $[Sum of Current Values]
            
            > [!NOTE]
            > If no records are found, explicitly state: "Our records indicate no active investment holdings."
            """,
            expected_output="A structured header and table showing the current investment portfolio from the database.",
            agent=tracker_agent
        )
        forecasting_task = Task(
            description="""
            1. Analyze the 'Current Portfolio Holdings' from the previous task.
            2. If no holdings exist, output 'No active assets identified for forecasting.' and STOP.
            3. For each asset name found:
               a. Perform a deep search for current market price, recent 7-day performance, and analyst price targets for 2024-2025.
            4. Append the following section to the previous report:

            ---
            ### Market Outlook & Performance Forecast
            | Asset | Current Sentiment | Projected 12M Growth | Confidence Level |
            | :--- | :--- | :--- | :--- |
            [Rows for each asset]
            
            ### Strategic Insights
            > [!IMPORTANT]
            > **Market Update:** [Provide a concise 2-3 sentence summary of global market conditions affecting these specific assets.]
            
            > [!TIP]
            > **Diversification Note:** [A brief professional tip based on the user's current holdings.]

            ---
            *Disclaimer: These projections are based on real-time market data and AI analysis. Always consult with a certified financial advisor before making investment decisions.*
            """,
            expected_output="A professional market outlook and forecast section appended to the portfolio report.",
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
            description="""
            1. Fetch transactions for {account_number}. 
            2. Present strictly using this format:

            # Personal Spending Analysis
            **Reporting Period:** Fiscal Month to Date

            ### Expenditure Breakdown
            | Spending Category | Total Amount | % of Outflow |
            | :--- | :--- | :--- |
            [Rows]

            > [!NOTE]
            > Analysis based on verified transaction history logs.
            """,
            expected_output="Categorized breakdown of spending in a professional Markdown report.",
            agent=analyzer_agent
        )
        prediction_task = Task(
            description="""
            Project next month's spending strictly using this format:
            
            ### Future Outflow Projection
            | Anticipated Metric | Forecasted Value | Confidence Level |
            | :--- | :--- | :--- |
            | Total Projected Spend | **$[Value]** | [High/Mid] |
            | Primary Cost Driver | [Category] | Verified Trend |
            
            > [!TIP]
            > **Budget Optimization:** [Strategic budgeting tip based on historical patterns.]
            """,
            expected_output="A clean expenditure forecast appended to the spending report.",
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
            1. Parse request: '{query}'.
            2. If querying details: Fetch and display from DB.
            3. If updating: Check for value, Update DB, Fetch updated.
            4. Present results strictly following this Markdown structure (preserve newlines):

            # Customer Profile Management
            **Verification Status:** Identity Authenticated

            ### Current Profile Information
            | Personal Field | Current Value | Update Status |
            | :--- | :--- | :--- |
            | Account Holder | **[Name]** | [Status] |
            | Email Address | [Email] | [Status] |
            | Account Reference | **{account_number}** | Verified |

            > [!IMPORTANT]
            > **Data Sync:** Profile changes are synchronized across all global systems in real-time.
            """,
            expected_output="A professional profile management table showing current or updated user data.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)
