from gdprfs.db_utils import Session
from gdprfs.models import File, Person, NameAlias
from sqlalchemy import and_, func
from gdprfs.merge_alerts import save_merge_alerts_for_ui
from Levenshtein import distance  # if installed


def _is_typo(a, b):
    # First try exact match
    if a == b:
        return True
    if len(a) > 1 and len(b) > 1: # avoid too short strings
        return distance(a, b) <= 3
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

        # detect partial matches that require internal confirmation
        alerts = []

        # Preload human-confirmed aliases to avoid spamming alerts
        known_aliases = {
            a.alias.lower()
            for a in s.query(NameAlias).all()
        }

        # Build a lookup: last name → registered user
        registered_people = {
            (p.first_name.lower(), p.last_name.lower()): p
            for p in s.query(Person).filter_by(registered=True)
        }

        for chunk in llm_results:
            for person_info in chunk["analysis"]["persons"]: # list of {name, is_known_user, user_id, confidence}
                if person_info["is_known_user"]: # if is_known_user = True
                    continue  # skip exact matches
                
                detected = person_info["name"].strip()
                detected_norm = detected.lower()

                # If this token is already a validated alias, skip creating an alert
                if detected_norm in known_aliases:
                    continue

                det_first, *rest = detected.split() # detect first and last names
                det_last = " ".join(rest) if rest else ""

                # check if last name matches a registered user
                for (first, last), reg_person in registered_people.items(): # iterate over registered users with the first and last names gotten
                    # check for last name match
                    if det_last.lower() == last.lower() or detected_norm == last.lower():
                        alerts.append({
                            "alias": detected,
                            "candidate": f"{reg_person.first_name} {reg_person.last_name}",
                            "person_id": reg_person.id
                        })
                    # check for first name match
                    if det_first.lower() == first.lower() or detected_norm == first.lower():
                        alerts.append({
                            "alias": detected,
                            "candidate": f"{reg_person.first_name} {reg_person.last_name}",
                            "person_id": reg_person.id
                        })
                    # if distance +-3 then a typo
                    if _is_typo(det_first.lower(), first.lower()):
                        alerts.append({
                            "alias": detected,
                            "candidate": f"{reg_person.first_name} {reg_person.last_name}",
                            "person_id": reg_person.id
                        })


        # If alerts exist → save for internal UI
        if alerts:
            save_merge_alerts_for_ui(path_abs, alerts)
            print(f"[LLM create merge alert] Merge alerts created for {path_abs}: {alerts}")

        s.commit()
        print(f"[LLM] Updated file_people for {len(file_obj.people)} persons")