import json
import sys, os

# import paths
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from LLManalyzer.agent import agent
from LLManalyzer.models import ChunkAnalysis
from gdprfs.models import Session, Person


def load_known_users():
    session = Session()
    people = session.query(Person).filter_by(registered=True).all()

    return [
        {"user_id": p.id, "full_name": f"{p.first_name} {p.last_name}"}
        for p in people
    ]


payload = {
    "text": "John Doe's email is john.doe@gmail.com",
    "known_users": load_known_users(),
}

# We pass JSON AS TEXT to the LLM
prompt = json.dumps(payload)

print("DEBUG: sending prompt =", prompt)

result = agent.run_sync(prompt)

raw = result.output
print("RAW OUTPUT:", raw)

parsed = ChunkAnalysis.model_validate(json.loads(raw))

print("STRUCTURED:", parsed)
print("DICT:", parsed.model_dump()) # to convert from Pydantic model to dict because json.dumps can't serialize Pydantic models directly
