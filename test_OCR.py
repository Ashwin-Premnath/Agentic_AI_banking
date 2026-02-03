from crewai import Agent, Task, Crew,LLM
from crewai_tools import OCRTool
from dotenv import load_dotenv
import os

load_dotenv()

tool = OCRTool()

llm = LLM(
    provider="nvidia",
    model="nvidia/nemoretriever-ocr-v1",
    api_key=os.getenv("NVIDIA_API_KEY"),
    base_url="https://ai.api.nvidia.com/v1/cv",
    temperature=0.0
)
agent = Agent(
    role="OCR Specialist",
    goal="Extract text from images",
    backstory="Vision‑enabled analyst",
    tools=[tool],
    llm=llm,
    verbose=True,
)

task = Task(
    description="Extract text from PAN_0441037396.png stored in Demo_kyc_docs folder",
    expected_output="All detected text in plain text",
    agent=agent,
)

crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()