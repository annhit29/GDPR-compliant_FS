from hashlib import sha256
import json
import os
from pathlib import Path
import requests
from gdprfs.models import File, Person, NameAlias, Session
from sqlalchemy import and_, func
from gdprfs.merge_alerts import save_merge_alerts_for_ui
from Levenshtein import distance  # if installed


def _is_typo(a, b):
    # First try exact match
    if a == b:
        return True
    if len(a) > 1 and len(b) > 1: # avoid too short strings
        dist = distance(a, b)
        print(f'{dist=}')
        print(f'{dist <= 3=}')
        return dist <= 3
    return False

def update_file_people_from_llm(path_abs: str, llm_results: list):
    """
    Given llm_results = list of chunk analyses,
    update File.people based on all persons found in all chunks.
    """

    print(f"[LLM] Updating DB mapping for file: {path_abs}")

    with Session() as s:
        # 1. Retrieve File entry
        file_obj = s.query(File).filter(File.abs_path == path_abs).first()
        if not file_obj:
            print(f"[LLM] File not in DB yet → creating entry")
            file_obj = File(abs_path=path_abs)
            s.add(file_obj)
            s.commit()

        # 2. Reset existing mapping
        file_obj.people.clear()

        # 3. For each chunk, add detected persons
        for chunk in llm_results:
            persons = chunk["analysis"]["persons"]
            for person_info in persons:
                name = person_info["name"].strip()
                first, *rest = name.split(" ")
                last = " ".join(rest) if rest else ""

                # Known user?
                if person_info["is_known_user"]:
                    person = s.query(Person).filter_by(id=person_info["user_id"]).first()
                else:
                    # First, check if this token is a known alias validated by the internal UI
                    alias_norm = name.strip().lower()
                    alias_row = (
                        s.query(NameAlias)
                        .filter(func.lower(NameAlias.alias) == alias_norm)
                        .first()
                    )
                    print(f'{alias_row=}')

                    if alias_row:
                        # Human already confirmed: alias → canonical person
                        person = s.get(Person, alias_row.person_id)
                        print(f"[LLM duplicate DS / alias already merged] Already-merged alias '{name}' which is the registered person id={person.id}")
                    else:
                        # Unknown → ensure entry exists in database
                        person = (
                            s.query(Person)
                            .filter(and_(Person.first_name == first, Person.last_name == last))
                            .first()
                        )
                        print(f'{person=}')
                        if not person:
                            person = Person(
                                first_name=first,
                                last_name=last,
                                uid=None,
                                registered=False
                            )
                            s.add(person)
                            s.commit()
                            print(f"[LLM unregistered DS] Added new unregistered user: {first} {last}")

                # Associate with file
                if person not in file_obj.people:
                    file_obj.people.append(person)

        # Preload human-confirmed aliases to avoid spamming alerts
        known_aliases = {
            a.alias.lower()
            for a in s.query(NameAlias).all()
        }

        # Build a lookup: last name → registered user
        registered_people = {
            (p.first_name.lower(), p.last_name.lower()): p
            for p in s.query(Person).filter_by(registered=True) #todo: or not? coz eg: "Hsieeh" won't create merge alert when whsieh hasn't registered yet
        }
        
        # 4. Create merge alerts for partial matches or potential typos
        # detect partial matches that require internal confirmation
        alerts = []
        for chunk in llm_results:
            for person_info in chunk["analysis"]["persons"]: # list of {name, is_known_user, user_id, confidence}
                if person_info["is_known_user"]: # if is_known_user = True
                    continue  # skip exact matches
                
                detected = person_info["name"].strip()
                detected_norm = detected.lower()

                # If this token is already a validated alias, skip creating an alert
                if detected_norm in known_aliases:
                    continue

                tokens = detected_norm.split()

                # todo: do this?
                # # When the detected name has only 1 token, treat it as last name, not first name
                # # This matches human intuition:
                # # A single surname like "Hsieh" or "Hsieeh" → likely a last name
                # # A single given name like "John" or "Johnn" → likely a first name
                # # Since you cannot know, you must pick one convention, and last-name is the correct one
                # # (because LLM is better at detecting surnames from partial input).

                # check if last name matches a registered user
                for (first, last), reg_person in registered_people.items(): # iterate over registered users with the first and last names gotten
                    # -----------------------------
                    # Case A: multi-token name
                    # Example: "J Doe", "John Doee"
                    # -----------------------------
                    if len(tokens) >= 2:
                        det_first = tokens[0].lower()
                        det_last  = tokens[-1].lower()

                        if _is_typo(det_first, first) or _is_typo(det_last, last):
                            print("Creating alert for multi-token name:", detected, "vs", reg_person.first_name, reg_person.last_name)
                            alerts.append({
                                "alias": detected,
                                "candidate": f"{reg_person.first_name} {reg_person.last_name}",
                                "person_id": reg_person.id
                            })

                    # -----------------------------
                    # Case B: single-token name
                    # Example: "Hsieeh", "Johnn", "Doee", "John", "Doe"
                    # -----------------------------
                    else:
                        word = tokens[0]

                        # Compare to first name
                        if _is_typo(word, first) or _is_typo(word, last):
                            print("Creating alert for single-token name:", detected, "vs", reg_person.first_name, reg_person.last_name)
                            alerts.append({
                                "alias": detected,
                                "candidate": f"{reg_person.first_name} {reg_person.last_name}",
                                "person_id": reg_person.id
                            })

        # If alerts exist → save for internal UI (with merge_alerts.json)
        if alerts:
            save_merge_alerts_for_ui(path_abs, alerts)
            print(f"[LLM create merge alert] Merge alerts created for {path_abs}: {alerts}")

        # 5. Extract GDPR Art 9 special data categories from all chunks
        # chunk["analysis"] comes from ChunkAnalysis.model_dump() in LLManalyzer/api.py
        # which now includes "special_data_categories" field (default [])
        all_special_cats = set()
        for chunk in llm_results:
            cats = chunk["analysis"].get("special_data_categories", [])
            all_special_cats.update(cats)
        file_obj.special_categories = ",".join(sorted(all_special_cats))
        if all_special_cats:
            print(f"[LLM Art9] Detected special data categories for {path_abs}: {all_special_cats}")

        s.commit()
        print(f"[LLM] Updated file_people for {len(file_obj.people)} persons")

def run_llm_analysis_and_update_db(path_abs: str):
    """
    Call the LLM analyzer for the given absolute file path,
    then update the gdprfs DB File.people accordingly.
    """
    print(f"[LLM] Running LLM analyzer on file: {path_abs}")

    # Skip temporary editor files
    if os.path.basename(path_abs).startswith(".goutputstream-"):
        print(f"[LLM] Skipping temp file for analysis: {path_abs}")
        return

    data = Path(path_abs).read_bytes()
    new_hash = sha256(data).hexdigest()
    
    # 1. Load known users from local DB
    with Session() as s:
        file_obj = s.query(File).filter_by(abs_path=path_abs).first()

        # If file exists and hash matches, skip expensive LLM
        if file_obj and file_obj.sha256 == new_hash:
            print(f"[LLM] SKIPPED — content unchanged (hash match).")
            return

        known_users = [
            {"user_id": person.id,
             "full_name": f"{person.first_name} {person.last_name}"}
            for person in s.query(Person).filter_by(registered=True)
        ]

    # 2. Call LLM analyzer API
    try:
        resp = requests.post(
            "http://127.0.0.1:5005/analyze-file",
            json={"path": path_abs, "known_users": known_users}
        )
        results = resp.json()
        
        print("[LLM] Raw analyzer result:")
        print(json.dumps(results, indent=2))

    except Exception as e:
        print(f"[LLM] ERROR: analyzer failed: {e}")
        return

    # 3. Update DB mapping (critical!)
    update_file_people_from_llm(path_abs, results)

    # 4. Store new hash in DB
    with Session() as s:
        file_obj = s.query(File).filter_by(abs_path=path_abs).first()
        if file_obj:
            file_obj.sha256 = new_hash
            s.commit()
            print(f"[LLM] Updated content hash for {path_abs}")