from pydantic import BaseModel, Field
from typing import Optional, Literal

class DepositIntent(BaseModel):
    """Classifies the user's intent."""
    intent: Literal["OPEN_DEPOSIT", "RENEW_DEPOSIT", "CHECK_RATES", "OTHER","GENERAL"] = Field(
        description="The category of the user's request."
    )
    confidence: float = Field(description="Confidence score between 0 and 1.")

class DepositFormData(BaseModel):
    """Structured data for opening a deposit."""
    amount: Optional[float] = Field(None, description="The deposit amount mentioned by user.")
    tenure_months: Optional[int] = Field(None, description="The tenure in months.")
    funding_account: Optional[str] = Field(None, description="The source account number or name.")
    certificate_id: Optional[str] = Field(None, description="Certificate ID for renewal requests.")
    missing_fields: list[str] = Field(default_factory=list, description="List of required fields still missing.")
    is_ready: bool = Field(False, description="True if all required fields are present and valid.")
    agent_response: str = Field(default="", description="The response message to send to the user.")