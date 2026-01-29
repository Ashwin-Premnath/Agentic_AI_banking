from crewai import Agent, Task, Crew, LLM, Process
from models import DepositIntent, DepositFormData
from tools import PDFGeneratorTool
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
tracing=True

nvidia_end_point="https://integrate.api.nvidia.com/v1"
PDF_tool=PDFGeneratorTool() 

llm = LLM(
    provider="openai",
    model="nvidia/nemotron-nano-12b-v2-vl",
    base_url=nvidia_end_point,
    stream=False
)

manager_LLM = LLM(
    provider="openai",
    model="mistralai/ministral-14b-instruct-2512",
    base_url=nvidia_end_point,
    
)

class DepositCrew:
    def __init__(self):
        self.support_agent = Agent(
            role="Senior Customer Support Representative",
            goal="Greet users and handle general inquiries or greetings.",
            backstory=(
                "You are the first point of contact. If the user says 'hi' or asks general questions "
                "not related to a transaction, provide a warm, professional response. "
                "If they want to open/renew/check rates, acknowledge and let them know you're assisting."
            ),
            llm=llm,
            verbose=True
        )
        self.intent_agent = Agent(
            role="Banking Intent Analyst",
            goal="Identify the user's specific banking goal naturally.",
            backstory=(
                "You are an expert listener. "
                "Classify as GENERAL if the user is just chatting or asking non-transactional questions. "
                "If the user says 'start', 'new', or 'put money in' or something similar, classify as OPEN_DEPOSIT. "
                "If they say 'renew', 'roll over', 'maturity', or 'extend' or someting similar, classify as RENEW_DEPOSIT. "
                "If they ask about 'rates', 'interest', or 'yield' or something similar, classify as CHECK_RATES."
                "Otherwise, use General non-transactional flow."
            ),
            llm=llm,
            verbose=True
        )
        self.form_agent = Agent(
            role="Conversational Banker",
            goal="Collect the correct information based on the specific intent.",
            backstory=(
                "You handle the conversation. "
                "1. If CHECK_RATES: Provide the rate table immediately (5% 1yr, 5.5% 2yr). "
                "2. If OPEN_DEPOSIT: Ask for Amount, Tenure, and Funding Account. "
                "3. If RENEW_DEPOSIT: Ask for the Certificate ID and the new Tenure."
            ),
            llm=llm,
            verbose=True
        )
        self.eligibility_agent = Agent(
            role="Compliance Officer",
            goal="Validate data and finalize the request.",
            backstory=(
                "You ensure all rules are met. "
                "Minimum deposit amount for any action is $500. "
                "For renewals, verify the Certificate ID format (mock check). "
                "Provide a clear success or error message."
            ),
            llm=llm,
            verbose=True
        )
        self.archivist_agent = Agent(
            role="Data Archivist",
            goal="Save transaction records to PDF files in categorized folders.",
            backstory=(
                "You are responsible for archiving all transactions. "
                "You MUST use the PDF Generator Tool to save records. "
                "Organize files into: open_deposits, renew_deposits, or rate_queries folders."
            ),
            tools=[PDF_tool],
            llm=llm,
            verbose=True
        )

        # --- Tasks ---

        self.support_task = Task(
            description="Address the user's input: '{user_input}'. Provide a professional greeting or response.",
            expected_output="A conversational response to the user.",
            agent=self.support_agent
        )
        self.classify_task = Task(
            description="Analyze user input: '{user_input}'. Classify as OPEN_DEPOSIT, RENEW_DEPOSIT, CHECK_RATES, or OTHER Classify intent. Use GENERAL for simple chat.",
            expected_output="Structured classification with intent and confidence score.",
            agent=self.intent_agent,
            output_pydantic=DepositIntent
        )

        self.form_task = Task(
            description="""
            You are a strict Data Extraction Specialist.
            
            Your goal is to populate the DepositFormData fields based on the user's intent and conversation.
            
            Context provided:
            1. User Input: {user_input}
            2. Conversation History: {history}
            3. Intent Classification Result will be automatically provided from the previous task
            
            INSTRUCTIONS:
            1. Analyze the Intent Classification Result from the previous task.
            2. SCRUTINIZE the User Input and Conversation History for specific data points.
            
            IF INTENT IS OPEN_DEPOSIT:
            - Search for the **Amount** (e.g., "5000", "$500", "five hundred dollars"). Assign to 'amount'.
            - Search for **Tenure** (e.g., "12 months", "1 year", "2 years"). Convert years to months. Assign to 'tenure_months'.
            - Search for **Funding Account** (e.g., "checking", "account 123", "savings"). Assign to 'funding_account'.
            
            IF INTENT IS RENEW_DEPOSIT:
            - Search for **Certificate ID**. Assign to 'certificate_id'.
            - Search for **Tenure**. Assign to 'tenure_months'.
            
            IF INTENT IS CHECK_RATES:
            - Set agent_response to the rate information
            - Set is_ready to True
            
            VALIDATION RULE:
            - Only add a field to 'missing_fields' if it is GENUINELY NOT FOUND in the User Input or History.
            - If you found the value in the text, POPULATE THE FIELD and DO NOT add it to missing_fields.
            
            RESPONSE GENERATION:
            - If 'missing_fields' is empty (all data found), set 'is_ready' to True and set 'agent_response' to a confirmation summary.
            - If 'missing_fields' has items, set 'is_ready' to False and set 'agent_response' to ask specifically for the missing items.
            
            DO NOT default to asking for everything. You must extract what is already provided.
            """,
            expected_output="Structured response with collected data or the next question.",
            agent=self.form_agent,
            output_pydantic=DepositFormData,
            context=[self.classify_task]
        )

        self.eligibility_task = Task(
            description="""
            You are a compliance officer finalizing the request.

            Use the DepositFormData from the previous task.

            - If is_ready is False (e.g. the agent just asked a question or provided rates):
              - Use agent_response from the previous step as the final answer to the user.

            - carefully look at the exported fields of the previous task output and use it if needed.

            - If is_ready is True:
              - Minimum deposit amount is $500.
              - For OPEN_DEPOSIT:
                - If amount is less than 500:
                  - Set agent_response to: "Sorry, the minimum deposit amount is $500."
                - If amount is 500 or more:
                  - Set agent_response to: "Success! We have opened your deposit of $[amount] for [tenure_months] months."
                  - Replace [amount] and [tenure_months] with actual values from the data.
              - For RENEW_DEPOSIT:
                - Set agent_response to: "Success! Certificate [certificate_id] has been renewed for [tenure_months] months."
                - Replace [certificate_id] and [tenure_months] with actual values from the data.
              - For CHECK_RATES:
                - Keep the agent_response from the form_task.

            Always respond with a plain text message in agent_response.
            """,
            expected_output="A short, clear text message to the user.",
            agent=self.eligibility_agent,
            context=[self.form_task]
        )
        
        self.save_record_task = Task(
            description="""
            You MUST save a PDF record of this transaction using the PDF Generator Tool.
            
            STEP 1: Examine the Intent from classify_task.
            Possible values: OPEN_DEPOSIT, RENEW_DEPOSIT, CHECK_RATES, OTHER, GENERAL
            
            STEP 2: Map intent to folder name:
            - OPEN_DEPOSIT → "open_deposits"
            - RENEW_DEPOSIT → "renew_deposits"  
            - CHECK_RATES → "rate_queries"
            - OTHER → "other_queries"
            - GENERAL → "general_queries"
            
            STEP 3: Build PDF content with ALL available data:
            ```
            BANKING TRANSACTION RECORD
            ==========================
            Date: {current_time}
            Intent: [intent from classify_task]
            
            Transaction Details:
            - Amount: [amount from form_task or N/A]
            - Tenure: [tenure_months from form_task or N/A]
            - Funding Account: [funding_account from form_task or N/A]
            - Certificate ID: [certificate_id from form_task or N/A]
            
            Final Response:
            [agent_response from eligibility_task]
            ```
            
            STEP 4: Generate filename in format: tx_20260128_143022
            Use current timestamp YYYYMMDD_HHMMSS
            
            STEP 5: CALL the PDF Generator Tool:
            Tool name: "PDF Generator Tool"
            Parameters:
            - content: [the formatted content from step 3]
            - filename: [the timestamp filename WITHOUT .pdf]
            - folder_name: [the folder from step 2]
            
            STEP 6: Show the formatted content from [agent_response from eligibility_task].
            
            CRITICAL: You MUST call the tool. Do not just describe what you would do.

            """,
            expected_output="agent_response from eligibility_task",
            agent=self.archivist_agent,
            context=[self.classify_task, self.form_task, self.eligibility_task],
            tools=[PDF_tool]
        )


        self.crew = Crew(
            agents=[self.support_agent, self.intent_agent, self.form_agent, self.eligibility_agent, self.archivist_agent],
            tasks=[self.support_task, self.classify_task, self.form_task, self.eligibility_task, self.save_record_task],
            process=Process.sequential,
            verbose=True,
            tracing=True,
        )

    def kickoff(self, user_input, history):
        now = datetime.now()
        current_time_str = now.strftime('%Y-%m-%d %H:%M:%S')
        current_time_file = now.strftime('%Y%m%d_%H%M%S')
        result = self.crew.kickoff(inputs={
            "user_input": user_input,
            "history": history,
            "current_time":current_time_str,
            "current_time_file": current_time_file
            })
        return result
