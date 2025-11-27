from enum import Enum
from pydantic import BaseModel
from typing import List, Optional

class Category(str, Enum):
    NAME = "Name"
    EMAIL = "Email"
    PHONE = "Phone"
    ADDRESS = "Address"
    CREDIT_CARD = "Credit Card"
    SOCIAL_SECURITY_NUMBER = "Social Security Number"
    IP_ADDRESS = "IP Address"
    OTHER = "Other"

class PersonHit(BaseModel):
    name: str
    is_known_user: bool
    user_id: Optional[int]
    confidence: float

class ChunkAnalysis(BaseModel):
    contains_personal_data: bool
    persons: List[PersonHit] #list of {name, is_known_user, user_id, confidence}
    categories: List[Category] #["Name", "Email", "Phone", "Address", ...]
    block_recommendation: bool # true if the file chunk should be blocked; false otherwise
    explanation: str
