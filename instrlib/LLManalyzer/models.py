from pydantic import BaseModel
from typing import List, Optional
class PersonHit(BaseModel):
    name: str
    is_known_user: bool
    user_id: Optional[int]
    confidence: float

class ChunkAnalysis(BaseModel):
    contains_personal_data: bool
    persons: List[PersonHit] #list of {name, is_known_user, user_id, confidence}
    categories: List[str] #["Name", "Email", "Phone", "Address", ...]
    block_recommendation: bool # true if the file chunk should be blocked; false otherwise
    explanation: str
