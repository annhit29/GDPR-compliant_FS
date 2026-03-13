import sys, os
# allow importing gdprfs.models from instrlib parent
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))


from pydantic_ai import Agent
from models import ChunkAnalysis
from dotenv import load_dotenv
import os
from pathlib import Path

# ------------------------------------------------------
# Load API key from .env
# ------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
ENV_PATH = CURRENT_DIR.parent / ".env"

load_dotenv(ENV_PATH)
assert os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY not found in .env"


# ------------------------------------------------------
# Pydantic-AI Agent (old version = no schema enforcement)
# ------------------------------------------------------

agent = Agent[ChunkAnalysis](
    model="gpt-5-nano",
    output_type=ChunkAnalysis,
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
----------------------------------------------update_file_people_from_llm

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
- Must match EXACT schema
----------------------------------------------
SPECIAL DATA CATEGORIES (GDPR Article 9)
----------------------------------------------
Also detect whether the text contains any GDPR Article 9 "special categories"
of personal data. If detected, populate the special_data_categories list with
the matching values. Use ONLY these exact values:

- "health" → medical conditions, diagnoses, prescriptions, symptoms, disabilities,
  mental health, hospital visits, health insurance, patient records
- "racial_ethnic" → race, ethnicity, skin color, national origin, ethnic background
- "political" → political opinions, party membership, voting preferences, political activism
- "religious" → religious beliefs, philosophical beliefs, church membership, spiritual practices
- "trade_union" → trade union membership, union activities
- "genetic" → genetic data, DNA, genome, hereditary conditions
- "biometric" → fingerprints, facial recognition data, iris scans, voiceprints
  (only when used to uniquely identify a person)
- "sex_life" → sexual orientation, sexual behavior, sex life data

If NONE of these categories are present, return an empty list [].

----------------------------------------------
TASK:
1. Analyze the JSON input.
2. Detect names, emails, phone numbers, identifiers.
3. Compare detected names/emails against input["known_users"].
4. Apply the confidence scoring rules.
5. Detect any GDPR Article 9 special data categories.
6. Fill the JSON fields accordingly.
"""
)