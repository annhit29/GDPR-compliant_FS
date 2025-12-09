import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from gdprfs.models import Person, Session
from sqlalchemy import func
import re

def extract_candidate_name_tokens(text: str):
    """
    Cheap name extractor.
    Returns tokens like ["Hsieh", "John", "Doe"].
    """
    tokens = re.findall(r"[A-Za-z]+", text)
    tokens = [t for t in tokens if len(t) > 1]  # remove single letters
    return tokens



def search_similar_users(tokens):
    """
    Given name tokens (like ["Hsieh", "John"]),
    search the DB for matching registered users.
    """
    results = []
    seen = set()

    with Session() as s:
        for tok in tokens:
            tok = tok.lower()

            matches = s.query(Person).filter(
                Person.registered == True,
                (
                    func.lower(Person.first_name).like(f"%{tok}%") |
                    func.lower(Person.last_name).like(f"%{tok}%")
                )
            ).all()

            for m in matches:
                if m.id not in seen:
                    seen.add(m.id)
                    results.append({
                        "user_id": m.id,
                        "full_name": f"{m.first_name} {m.last_name}"
                    })

    return results
