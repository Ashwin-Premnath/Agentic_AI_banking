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

file_read_tool = FileReadTool(
    name="File Reader",
    description="Reads the content of a file and returns it as a string.",
    file_path="policies\\bank_policies.md"
)

interest_policy_tool = FileReadTool(
    name="Interest Policy Reader",
    description="Reads the content of the interest rate file and returns it as a string.",
    file_path="policies\\interest_rate.txt"
)   
class NL2SQLTool(BaseTool):
    """Enhanced SQL tool with better error handling and query validation"""
    name: str = "NL2SQL Database Tool"
    description: str = (
        "Execute SQL queries on the bank's SQLite database. "
        "PROVIDE A VALID SQL QUERY AS INPUT. "
        "The tool executes SQL and returns results as JSON-formatted list of dictionaries. "
        "\n\nDATABASE SCHEMA:"
        "\n- customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT, account_number TEXT UNIQUE, balance REAL)"
        "\n- transactions (id INTEGER PRIMARY KEY, account_number TEXT, receiver_account_number TEXT, transaction_type TEXT, mode_of_payment TEXT, amount REAL, timestamp DATETIME)"
        "\n- investments (id INTEGER PRIMARY KEY, account_number TEXT, asset_name TEXT, asset_type TEXT, invested_amount REAL, current_value REAL, timestamp DATETIME)"
        "\n\nRELATIONSHIPS: All tables link via 'account_number' field."
        "\n\nEXAMPLE QUERIES:"
        "\n- SELECT * FROM customers WHERE account_number = 'ACC123456'"
        "\n- SELECT * FROM transactions WHERE account_number = 'ACC123456' ORDER BY timestamp DESC LIMIT 5"
        "\n- INSERT INTO investments (account_number, asset_name, asset_type, invested_amount, current_value, timestamp) VALUES ('ACC123456', 'Apple Stock', 'equity', 5000.0, 5200.0, datetime('now'))"
        "\n- UPDATE customers SET balance = 15000.0 WHERE account_number = 'ACC123456'"
    )
    db_path: str = "bank_system_v3.db"

    def _run(self, query: str) -> str:
        import sqlite3
        import os
        import json
        
        try:
            # Clean the SQL query
            sql = query.strip()
            sql = sql.replace("```sql", "").replace("```", "").replace("`", "").strip()
            
            if not os.path.exists(self.db_path):
                return json.dumps({
                    "error": f"Database file '{self.db_path}' not found in current directory.",
                    "success": False
                })

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            print(f"--- EXECUTING SQL: {sql} ---")
            cursor.execute(sql)
            conn.commit()
            
            # Check if it was a SELECT query or a modification query
            if cursor.description:
                rows = cursor.fetchall()
                print(f"--- SQL RESULT: Found {len(rows)} rows ---")
                
                # Convert to list of dictionaries
                results = [dict(row) for row in rows]
                conn.close()
                
                if not results:
                    return json.dumps({
                        "data": [],
                        "message": "NO_RECORDS_FOUND",
                        "success": True
                    })
                
                return json.dumps({
                    "data": results,
                    "count": len(results),
                    "success": True
                })
            else:
                # It was an UPDATE, INSERT, or DELETE
                affected = cursor.rowcount
                conn.close()
                return json.dumps({
                    "message": f"Query executed successfully. {affected} rows affected.",
                    "rows_affected": affected,
                    "success": True
                })
                
        except sqlite3.Error as e:
            return json.dumps({
                "error": f"SQL Error: {str(e)}. Please check your query syntax.",
                "success": False
            })
        except Exception as e:
            return json.dumps({
                "error": f"Unexpected error: {str(e)}",
                "success": False
            })


class DatabaseSchemaInfoTool(BaseTool):
    """Tool to get database schema information"""
    name: str = "Database Schema Info"
    description: str = (
        "Get detailed schema information about database tables. "
        "Input: table name (customers, transactions, or investments). "
        "Returns: column names, data types, and constraints for the specified table."
    )
    db_path: str = "bank_system_v3.db"

    def _run(self, table_name: str) -> str:
        import sqlite3
        import json
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get table info
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            if not columns:
                conn.close()
                return json.dumps({
                    "error": f"Table '{table_name}' not found",
                    "success": False
                })
            
            schema_info = {
                "table_name": table_name,
                "columns": [
                    {
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "primary_key": bool(col[5])
                    }
                    for col in columns
                ],
                "success": True
            }
            
            conn.close()
            return json.dumps(schema_info, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Error fetching schema: {str(e)}",
                "success": False
            })


class QueryGeneratorTool(BaseTool):
    """Tool to help generate SQL queries from natural language"""
    name: str = "SQL Query Generator"
    description: str = (
        "Generate SQL query templates from natural language descriptions. "
        "Input: Natural language description of what you want to query. "
        "Examples: "
        "'get balance for account ACC123456' -> SELECT balance FROM customers WHERE account_number = 'ACC123456'; "
        "'get last 5 transactions for ACC123456' -> SELECT * FROM transactions WHERE account_number = 'ACC123456' ORDER BY timestamp DESC LIMIT 5; "
        "'add new investment' -> INSERT INTO investments (...) VALUES (...)"
    )

    def _run(self, description: str) -> str:
        import json
        
        description_lower = description.lower()
        templates = {
            "balance": "SELECT balance FROM customers WHERE account_number = '{account_number}'",
            "customer info": "SELECT * FROM customers WHERE account_number = '{account_number}'",
            "all customers": "SELECT * FROM customers",
            "recent transactions": "SELECT * FROM transactions WHERE account_number = '{account_number}' ORDER BY timestamp DESC LIMIT {limit}",
            "all transactions": "SELECT * FROM transactions WHERE account_number = '{account_number}' ORDER BY timestamp DESC",
            "investments": "SELECT * FROM investments WHERE account_number = '{account_number}'",
            "total balance": "SELECT SUM(balance) as total_balance FROM customers",
            "update balance": "UPDATE customers SET balance = {new_balance} WHERE account_number = '{account_number}'",
            "insert customer": "INSERT INTO customers (name, email, account_number, balance) VALUES ('{name}', '{email}', '{account_number}', {balance})",
            "insert transaction": "INSERT INTO transactions (account_number, receiver_account_number, transaction_type, mode_of_payment, amount, timestamp) VALUES ('{account_number}', '{receiver}', '{type}', '{mode}', {amount}, datetime('now'))",
            "insert investment": "INSERT INTO investments (account_number, asset_name, asset_type, invested_amount, current_value, timestamp) VALUES ('{account_number}', '{asset_name}', '{asset_type}', {invested_amount}, {current_value}, datetime('now'))"
        }
        
        # Find matching template
        matched_template = None
        for key, template in templates.items():
            if key in description_lower:
                matched_template = template
                break
        
        if matched_template:
            return json.dumps({
                "template": matched_template,
                "note": "Replace placeholders {like_this} with actual values",
                "success": True
            })
        else:
            return json.dumps({
                "message": "No exact template match found. Common patterns available:",
                "available_patterns": list(templates.keys()),
                "success": True
            })


def get_sql_tool(db_path="bank_system_v3.db"):
    """Get the main SQL execution tool"""
    return NL2SQLTool(db_path=db_path)


def get_schema_tool(db_path="bank_system_v3.db"):
    """Get the schema information tool"""
    return DatabaseSchemaInfoTool(db_path=db_path)


def get_query_generator_tool():
    """Get the query generator helper tool"""
    return QueryGeneratorTool()


class BankingCrews:
    def __init__(self, account_number=None):
        self.account_number = account_number
        self.db_path = "bank_system_v3.db"
        self.user_dir = f"user_data/{account_number}" if account_number else "user_data"
        self.uploads_dir = f"{self.user_dir}/uploads"
        
        # Initialize all database tools
        self.sql_tool = get_sql_tool(self.db_path)
        self.schema_tool = get_schema_tool(self.db_path)
        self.query_gen_tool = get_query_generator_tool()
        
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
            verbose=True,
            tools=[FileWriterTool()]
        )
        task = Task(
            description="""
            Save the verified KYC data from '{pending_data}' to the file path '{processed_path}'.
            Confirm successful storage with a professional message.
            """,
            expected_output="Confirmation message of successful KYC data storage.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def onboarding_data_crew(self):
        agent = Agent(
            role="New Account Registration Specialist",
            backstory="Friendly onboarding specialist who collects customer details for new account creation.",
            goal="Gather complete registration details from the user in a conversational manner.",
            llm=standard_llm,
            verbose=True
        )
        task = Task(
            description="""
            Extract registration data from: '{query}'.
            Required fields: Full Name, Email, Initial Deposit Amount.
            
            If ALL fields are present, format as:
            | Field | Value |
            | :--- | :--- |
            | Full Name | [Name] |
            | Email Address | [Email] |
            | Account Number | [Auto-generated: ACC + timestamp] |
            | Initial Balance | $[Amount] |
            
            If ANY field is missing, ask for it conversationally.
            """,
            expected_output="Either a complete registration table OR a friendly request for missing information.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def onboarding_storage_crew(self):
        """Enhanced onboarding storage with database integration"""
        agent = Agent(
            role="Account Registration Database Manager",
            backstory="Database specialist who creates new customer accounts in the banking system with precision and security.",
            goal="Insert new customer data into the database and confirm successful account creation.",
            llm=standard_llm,
            tools=[self.sql_tool, FileWriterTool()],
            verbose=True
        )
        task = Task(
            description="""
            Process verified onboarding data from '{verified_data}'.
            4
            STEPS:
            1. Parse the verified data table to extract: Full Name, Email, Account Number, Initial Balance
            2. Generate SQL INSERT query:
               INSERT INTO customers (name, email, account_number, balance) 
               VALUES ('[name]', '[email]', '[account_number]', [balance])
            3. Execute the SQL query using the NL2SQL Database Tool
            4. Verify insertion by querying: SELECT * FROM customers WHERE account_number = '[account_number]'
            5. Save backup JSON to user_data/[account_number]/profile.json
            
            RESPONSE FORMAT (Strict Markdown Table):
            # Account Creation Successful 
            
            **Welcome Aboard!** Your account has been created and activated.
            
            ### Account Details
            | Field | Value |
            | :--- | :--- |
            | Account Holder | [Name] |
            | Account Number | **[Account Number]** |
            | Email | [Email] |
            | Opening Balance | **$[Balance]** |
            
            > [!SUCCESS]
            > Your account is now active in our banking system. You can start using all our services immediately.
            """,
            expected_output="Confirmation of database insertion with complete account details.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def account_crew(self):
        """
        Robust Account Crew designed to prevent hallucinations and handle empty data states.
        Follows strict Streamlit Markdown table standards.
        """
        agent = Agent(
            role="Senior Account Information Specialist",
            backstory=(
                "You are a precise banking data analyst. You NEVER guess or fabricate numbers. "
                "If the database has no data, you report that clearly. "
                "You format all outputs using clean Markdown tables compatible with Streamlit."
            ),
            goal="Provide accurate account information for {account_number} using database queries.",
            llm=standard_llm,
            tools=[self.sql_tool, self.schema_tool, self.query_gen_tool],
            verbose=True
        )

        task = Task(
            description=(
                "User Query: '{query}'\n"
                "Target Account: {account_number}\n\n"
                
                "### Step 1: Execute Database Queries\n"
                "Run the following queries using the SQL Tool:\n"
                "1. Profile: `SELECT * FROM customers WHERE account_number = '{account_number}'`\n"
                "2. Transactions: `SELECT * FROM transactions WHERE account_number = '{account_number}' ORDER BY timestamp DESC LIMIT 5`\n"
                "3. Investments: `SELECT * FROM investments WHERE account_number = '{account_number}'`\n\n"
                
                "### Step 2: Format Output (Strict Markdown Table)"
                "Use the following format exactly. Do not change headers.\n\n"
                
                "# Account Executive Summary\n\n"
                "output should be strictly in markdown table format"
                "### Profile Snapshot\n"
                "| Field | Details |\n"
                "| :--- | :--- |\n"
                "| Account Holder | [Name from DB] |\n"
                "| Account Number | **{account_number}** |\n"
                "| Email | [Email from DB] |\n"
                "| Account Status | Active |\n\n"
                
                "### Financial Overview\n"
                "use data from customers table,transactions table and investments table and investments table to calculate the following:\n"
                "| Metric | Value |\n"
                "| :--- | :--- |\n"
                "| Available Balance | **$[Balance]** |\n"
                "| Total Assets | $[Total Assets] |\n"
                "| Net Worth | $[Net Worth] |\n\n"
                
                "### Recent Transactions (Last 5)\n"
                "use data from transactions table"
                "| Date | Type | Amount | Mode |\n"
                "| :--- | :--- | :--- | :--- |\n"
                "[If DB has data: assign Date to timestamp, type for transaction_type, amount as amount, mode as mode_of_payment]"
                "[If DB is empty: | - | - | - | - |]\n\n"
                
                "CRITICAL: if the database has no data, explicitly state so and show $0.00."
                "[If DB has NO investment data in the database:]\n"
                "**Status:** No active investments found in portfolio.\n"
            ),
            expected_output=(
                "A professional summary. If no investments exist, explicitly state so and show $0.00. "
                "No fake data allowed."
            ),
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def market_analysis_crew(self):
        agent = Agent(
            role="Global Market Analyst",
            backstory="Financial expert tracking worldwide market trends, stock prices, and economic indicators.",
            goal="Provide real-time market analysis and investment insights.",
            llm=standard_llm,
            tools=[serper_tool],
            verbose=True
        )
        task = Task(
            description="""
            Research: '{query}'
            
            Provide market analysis with:
            1. Current market status/stock prices
            2. Recent trends and movements
            3. Expert recommendations
            
            Format as professional market report.
            """,
            expected_output="Market analysis report with current data and insights.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def interest_calculator_crew(self):
        """Enhanced interest calculator with database integration"""
        agent = Agent(
            role="Financial Returns Calculator",
            backstory="""Expert at calculating returns, interest, and growth projections. 
            When users ask about returns on an amount, you calculate and optionally store as investment.""",
            goal="Calculate investment returns and project growth for account {account_number}.",
            llm=standard_llm,
            tools=[self.sql_tool],
            verbose=True
        )
        task = Task(
            description="""
            Query: '{query}' | Account: {account_number}
            
            CALCULATION STEPS:
            1. Parse the investment amount and duration from query
            2. Calculate returns using standard rates (e.g., 7% annual for equities, 5% for FD)
            3. If user wants to track this investment:
               - Generate INSERT query for investments table
               - Store: asset_name, asset_type, invested_amount, projected current_value
            
            RESPONSE FORMAT (Strict Markdown Table):
            # Investment Returns Calculation
            
            ### Projection Details
            | Parameter | Value |
            | :--- | :--- |
            | Principal Amount | $[Amount] |
            | Investment Duration | [Duration] |
            | Expected Annual Return | [Rate]% |
            | Projected Value | **$[Calculated]** |
            | Expected Profit | **$[Profit]** |
            
            > [!TIP]
            > Would you like me to track this investment in your portfolio?
            """,
            expected_output="Detailed returns calculation with optional database storage.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def doc_management_crew(self):
        agent = Agent(
            role="Document Manager",
            backstory="Organized specialist managing customer document uploads and records.",
            goal="List and manage uploaded documents for the user.",
            llm=standard_llm,
            tools=[DirectoryReadTool(), DirectorySearchTool()],
            verbose=True
        )
        task = Task(
            description="""
            List all files in: '{uploads_dir}'
            
            Format as organized document inventory with file names, types, and dates.
            """,
            expected_output="Professional document listing.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def interest_calculator_crew(self):

        policy_reader = FileReadTool()

        agent = Agent(
            role="Policy Interest Calculator",
            backstory=(
                "You are a banking calculator who strictly follows company policy. "
                "You NEVER guess interest rates. You always read the policy file first to find the correct rates. "
            ),
            goal="Read the company policy file and calculate returns strictly based on those rates.",
            llm=standard_llm,
            tools=[policy_reader],
            verbose=True
        )

        task = Task(
            description=f"""
            User Query: '{{query}}' | Account: {{account_number}}
            
            ### Step 1: Read Company Policy
            Read the policy file located at: 'policies\\Interest_rate.txt'
            
            ### Step 2: Parse Rates
            Identify the product (Savings, FD, RD) and tenure. Extract the rate from the file.
            
            ### Step 3: Calculate
            1. Principal Amount: [Parse from query]
            2. Tenure: [Parse from query]
            3. Rate: [From File]
            4. Calculate Simple Interest and Maturity Value.
            
            ### Step 4: Output Format
            # Interest Rate Calculation Report
            ### Policy Parameters Applied
            | Parameter | Value |
            | :--- | :--- |
            | Product Type | [Savings / FD / RD] |
            | Tenure | [Duration] |
            | Policy Rate Applied | [X]% p.a. |
            
            ### Calculation Breakdown
            | Metric | Value |
            | :--- | :--- |
            | Principal Amount | $[Amount] |
            | Total Interest Earned | $[Interest] |
            | Maturity Value | **$[Total]** |
            """,
            expected_output="A calculation report proving which rate from the policy file was used.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def policy_crew(self):

        policy_reader = FileReadTool()

        agent = Agent(
            role="Banking Policy Expert",
            backstory=(
                "Knowledge specialist for bank policies, terms, FD rates, and general banking information. "
                "You answer in a professional and concise manner and answer only the query asked."
            ),
            goal="Provide accurate policy and general banking information professionally and structured.",
            llm=standard_llm,
            tools=[policy_reader],
            verbose=True
        )

        task = Task(
            description="""
            Policy Query: '{query}'
            
            ### Step 1: Retrieve Policy Information
            Read the policy file located at: 'policies\\bank_policies.md'
            
            ### Step 2: Formulate Response
            Answer ONLY the question asked. Be brief and to the point.
            
            ### Step 3: Output Format
            ### Policy Information
            **Query:** [User's Question]
            **Answer:** [Provide the concise answer here]
            """,
            expected_output="Clear policy information with proper formatting.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def fd_crew(self):
        """Enhanced FD processing with database integration"""
        agent = Agent(
            role="Fixed Deposit Application Processor",
            backstory="""Specialist in processing FD applications. You extract data from forms and create FD records.
            You work conversationally to gather all required information.""",
            goal="Process FD application and store in database.",
            llm=vision_llm,
            tools=[self.sql_tool],
            verbose=True
        )
        task = Task(
            description="""
            Process FD application from file: '{file_path}'
            User context: '{user_context}'
            Previous data: '{accumulated_data}'
            
            STEPS:
            1. Extract FD details: Amount, Duration, Interest Rate, Maturity Date
            2. If any field missing, ask conversationally
            3. When all data collected, format preview:

             OUTPUT FORMAT (Strict Markdown Table):

            # Fixed Deposit Application Preview
            | Field | Value |
            | :--- | :--- |
            | Account Number | {account_number} |
            | FD Amount | $[Amount] |
            | Duration | [Months/Years] |
            | Interest Rate | [Rate]% |
            | Maturity Date | [Date] |
            | Maturity Value | $[Calculated] |
            
            Is this correct? Reply 'Yes' to create the FD.
            
            4. On confirmation, INSERT into investments table with asset_type='FD'
            """,
            expected_output="FD preview OR confirmation message after database insertion.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    def investment_crew(self):
        """Enhanced investment tracking with comprehensive database operations"""
        tracker_agent = Agent(
            role="Investment Portfolio Database Manager",
            backstory="""Database specialist managing investment portfolios. 
            You execute precise SQL queries to track, update, and retrieve investment data.
            You NEVER fabricate data - only work with actual database records.""",
            goal="Manage investment portfolio for {account_number} using database operations.",
            llm=standard_llm,
            tools=[self.sql_tool, self.schema_tool],
            verbose=True
        )
        forecaster_agent = Agent(
            role="Asset Growth Forecaster",
            backstory="""Financial analyst who enriches real portfolio data with market trends.
            You ONLY forecast for assets that actually exist in the database.""",
            goal="Provide growth forecasts for actual investments.",
            llm=standard_llm,
            tools=[serper_tool],
            verbose=True
        )
        
        report_date = datetime.now().strftime("%Y-%m-%d")
        
        tracking_task = Task(
            description=f"""
            Query: '{{query}}' | Account: {{account_number}}
            
            STEP 1 - Handle Buy Requests:
            If query contains 'buy', 'invest', or 'purchase':
               a. Parse: asset name, asset type, amount invested
               b. Set current_value = invested_amount (initial)
               c. Execute: INSERT INTO investments (account_number, asset_name, asset_type, invested_amount, current_value, timestamp) 
                          VALUES ('{{account_number}}', '[asset]', '[type]', [amount], [amount], datetime('now'))
               d. Confirm insertion
            
            STEP 2 - Fetch Portfolio:
            Execute: SELECT * FROM investments WHERE account_number = '{{account_number}}'
            
            STEP 3 - Return Format:
            Return ONLY the raw JSON from the database query result.
            Example: {{"data": [{{"asset_name": "Apple", "invested_amount": 5000.0}}], "success": true}}
            
            If no records: {{"data": [], "message": "NO_RECORDS_FOUND", "success": true}}
            """,
            expected_output="Raw JSON response from database query.",
            agent=tracker_agent
        )
        
        forecasting_task = Task(
            description=f"""
            Input: Raw JSON from Tracker Agent
            
            SCENARIO A - Active Portfolio:
            Parse JSON and format strictly as:
            
            # Investment Portfolio Statement
            **As of Date:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
            **Account:** {{account_number}}

            OUTPUT FORMAT (Strict Markdown Table):

            ### Portfolio Holdings
            | Asset Name | Type | Cost Basis | Market Value | Gain/Loss ($) | Return (%) |
            | :--- | :--- | :--- | :--- | :--- | :--- |
            [Row example: | Apple Inc. | Stock | $5,000.00 | $5,450.00 | $450.00 | +9.0% |]
            
            ### Portfolio Summary
            | Metric | Value |
            | :--- | :--- |
            | Total Invested | $[Sum invested_amount] |
            | Total Market Value | $[Sum current_value] |
            | **Total Profit/Loss** | **$[Difference]** |
            
            **Info:** Performance data is based on current market inputs.
            
            SCENARIO B - No Holdings:
            # Portfolio Status
            You currently do not hold any assets in your investment portfolio.
            """,
            expected_output="Professional brokerage-style table of investments.",
            agent=forecaster_agent,
            context=[tracking_task]
        )
        return Crew(agents=[tracker_agent, forecaster_agent], tasks=[tracking_task, forecasting_task], verbose=True)

    def spending_forecast_crew(self):
        """Enhanced spending analysis with detailed breakdowns and confidence scoring"""
        analyzer_agent = Agent(
            role="Spending Pattern Analyst",
            backstory="""Transaction data specialist who analyzes spending patterns using database queries.
            You categorize expenses and identify trends from real transaction data.
            You provide detailed metrics including averages and percentages.""",
            goal="Analyze spending patterns for {account_number} from transaction history.",
            llm=standard_llm,
            tools=[self.sql_tool, self.schema_tool],
            verbose=True
        )
        
        predictor_agent = Agent(
            role="Expense Predictor",
            backstory="Financial forecasting specialist who predicts future spending based on historical patterns and calculates confidence scores.",
            goal="Predict next month's spending based on transaction analysis.",
            llm=standard_llm,
            verbose=True
        )
        
        # ==========================================
        # Task 1: Historical Analysis
        # ==========================================
        analysis_task = Task(
            description=f"""
            Account: {{account_number}}
            
            STEP 1 - Fetch Transactions:
            Execute: SELECT transaction_type, mode_of_payment, amount, timestamp 
                    FROM transactions 
                    WHERE account_number = '{{account_number}}' 
                    ORDER BY timestamp DESC LIMIT 50
            
            STEP 2 - Detailed Analysis Logic:
            Group the data by 'transaction_type'.
            For EACH group, calculate:
            1. Total Spent
            2. Number of Transactions (Count)
            3. Average Transaction Value (Total / Count)
            4. Percentage of Total Outflow
            
            STEP 3 - Output Format (Strict Markdown Table):
            
            # Spending History Analysis
            **Account:** {{account_number}} | **Period:** Last 50 Transactions
            
            ### Historical Spending Breakdown
            | Transaction Type | Total Spent | Count | Avg. Transaction | % of Total |
            | :--- | :--- | :--- | :--- | :--- |
            [Row example: | WITHDRAWAL | $5,000.00 | 15 | $333.33 | 60% |]
            [Row example: | TRANSFER | $2,000.00 | 4 | $500.00 | 24% |]
            
            **Total Verified Outflow:** $[Sum of all amounts]
            **Transaction Volume:** [Total count] transactions
            
            [If no transactions found:]
            | Transaction Type | Total Spent | Count | Avg. Transaction | % of Total |
            | :--- | :--- | :--- | :--- | :--- |
            | - | $0.00 | 0 | $0.00 | 0% |
            
            **Note:** Insufficient data for analysis.
            """,
            expected_output="Detailed analysis table with Total, Count, Average, and Percentage.",
            agent=analyzer_agent
        )
        
        prediction_task = Task(
            description="""
            Based on the spending analysis from the previous task:
            
            STEP 1 - Forecasting Logic:
            1. Analyze the trend (Is spending increasing or decreasing based on recent vs older data?).
            2. Predict next month's spend for EACH category based on historical averages and trend.
            3. Calculate a Confidence Score:
               - **High (85-100%):** High transaction volume (>20) with consistent patterns.
               - **Medium (50-84%):** Moderate volume (10-20) or slight variance.
               - **Low (<50%):** Low volume (<10) or highly volatile spending.
            
            STEP 2 - Output Format (Strict Markdown Table):
            
            # Future Spending Forecast
            **Forecast Period:** Next 30 Days
            
            ### Projection Breakdown
            | Category | Projected Spend | Variance vs. Avg. | Reasoning |
            | :--- | :--- | :--- | :--- |
            [Row example: | WITHDRAWAL | $5,500.00 | +$500.00 | Upward trend detected |]
            [Row example: | TRANSFER | $2,100.00 | +$100.00 | Stable monthly average |]
            
            ### Forecast Summary
            | Metric | Value |
            | :--- | :--- |
            | **Total Projected Spend** | **$[Sum of projections]** |
            | **Confidence Score** | **[High/Medium/Low] ([X]%)** |
            | Recommendation | [e.g., Monitor withdrawal trend] |
            
            > [!NOTE]
            > Forecast based on historical pattern analysis. Actual future spending may vary.
            """,
            expected_output="Detailed forecast table with projections, variance, and a calculated confidence score.",
            agent=predictor_agent,
            context=[analysis_task]
        )
        
        return Crew(agents=[analyzer_agent, predictor_agent], tasks=[analysis_task, prediction_task], verbose=True)
    def account_management_crew(self):
        """Enhanced account management with database updates"""
        agent = Agent(
            role="Account Profile Administrator",
            backstory="""Senior database administrator with authority to update customer profiles.
            You execute precise SQL UPDATE queries and verify all changes.
            You NEVER fabricate data and ALWAYS confirm successful updates.""",
            goal="Manage customer profile for {account_number} with database precision.",
            llm=standard_llm,
            tools=[self.sql_tool, self.schema_tool],
            verbose=True,
            allow_delegation=False
        )

        task = Task(
            description=f"""
            Query: '{{query}}' | Account: {{account_number}}
            
            WORKFLOW:
            1. Execute SQL to update the profile (UPDATE customers SET ...)
            2. Execute SQL to verify the change (SELECT * FROM customers ...)
            
            OUTPUT FORMAT (Strict Markdown Table):
            
            # Profile Update Confirmation
            
            ### Updated Information
            | Field | New Value |
            | :--- | :--- |
            | Full Name | [Name] |
            | Email Address | [Email] |
            | Account Number | {{account_number}} |
            | Last Updated | [Timestamp] |
            
            Your changes have been saved securely to the database.
            """,
            expected_output="A confirmation summary in a table format.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)