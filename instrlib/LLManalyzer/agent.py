import sys, os
# allow importing gdprfs.models from instrlib parent
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))


from pydantic_ai import Agent
from instrlib.LLManalyzer.models import ChunkAnalysis
from dotenv import load_dotenv
import os
from pathlib import Path

# ------------------------------------------------------
# Load API key from .env
# ------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
ENV_PATH = CURRENT_DIR.parent.parent / ".env"

load_dotenv(ENV_PATH)
assert os.getenv("OPENAI_API_KEY"), "❌ OPENAI_API_KEY not found in .env"


# ------------------------------------------------------
# Pydantic-AI Agent (old version = no schema enforcement)
# ------------------------------------------------------

agent = Agent[ChunkAnalysis](
    model="gpt-5-nano",
instructions="""
You will receive a **JSON string** as the user prompt.
Parse this JSON into two fields:

- text: the text chunk to analyze
- known_users: list of {"user_id": int, "full_name": str}
Example of what you will receive (as a string):
{"text": "...", "known_users": [...]}


----------------------------------------------
HOW TO USE THE INPUT
----------------------------------------------
After parsing the JSON string, use:

text = parsed_json["text"]
known_users = parsed_json["known_users"]

----------------------------------------------
CONFIDENCE SCORING RULES (for not have inventing confidence scores)
----------------------------------------------

### Name confidence:
- 0.95 - 1.00 → exact match of known user's full_name (case-insensitive)
- 0.85 - 0.95 → strong partial match (full name detected but with noise)
- 0.60 - 0.85 → one part matches (first OR last name)
- 0.30 - 0.60 → weak or fuzzy match
- <0.30 → probably not a person

### Email confidence:
- 0.95 - 1.00 → valid email pattern (contains '@' and domain)
- 0.75 - 0.95 → looks like email but slightly malformed
- 0.40 - 0.75 → uncertain email-like token
- <0.40 → not an email

### Known user matching:
If full_name matches EXACTLY (case-insensitive):
- is_known_user = true
- user_id = that ID
- confidence >= 0.95


----------------------------------------------
OUTPUT FORMAT (MUST BE STRICT JSON)
----------------------------------------------

STRICT OUTPUT RULES:
- Output ONLY valid JSON
- No text outside the JSON object
- No markdown, no comments
- Must match EXACT schema:

{
  "contains_personal_data": bool,
  "persons": [
    {
      "name": str,
      "is_known_user": bool,
      "user_id": int | null,
      "confidence": float
    }
  ],
  "categories": [str],
  "block_recommendation": bool,
  "explanation": str
}

TASK:
1. Analyze the JSON input.
2. Detect names, emails, phone numbers, identifiers.
3. Compare detected names/emails against input["known_users"].
4. Apply the confidence scoring rules.
5. Fill the JSON fields accordingly.
"""
)