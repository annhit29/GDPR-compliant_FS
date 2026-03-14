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

# GDPR Article 9 — special categories of personal data
class SpecialDataCategory(str, Enum):
    HEALTH = "health"
    RACIAL_ETHNIC = "racial_ethnic"
    POLITICAL = "political"
    RELIGIOUS = "religious"
    TRADE_UNION = "trade_union"
    GENETIC = "genetic"
    BIOMETRIC = "biometric"
    SEX_LIFE = "sex_life"

class PersonHit(BaseModel):
    name: str
    is_known_user: bool
    user_id: Optional[int]
    confidence: float
    special_data_categories: List[SpecialDataCategory] = []  # Art 9 categories that apply specifically to THIS person

class ChunkAnalysis(BaseModel):
    contains_personal_data: bool
    persons: List[PersonHit] #list of {name, is_known_user, user_id, confidence}
    categories: List[Category] #["Name", "Email", "Phone", "Address", ...]
    special_data_categories: List[SpecialDataCategory] = [] # GDPR Art 9 special categories detected in this chunk
    block_recommendation: bool # true if the file chunk should be blocked; false otherwise
    explanation: str
