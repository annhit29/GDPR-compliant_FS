from flask import Flask, request, Response #jsonify
from splitter import split_file
from agent import agent
import json
from llm_utils import extract_candidate_name_tokens, search_similar_users

app = Flask(__name__)

@app.post("/analyze-file")
def analyze_file():
    data = request.json
    path = data["path"]
    # known_users = data.get("known_users", []) # <- wanna scale up, so

    # STEP 1: read raw file text for fast extraction
    with open(path, "r", errors="ignore") as f:
        full_text = f.read()

    candidate_tokens = extract_candidate_name_tokens(full_text)
    print(f'{candidate_tokens=}')

    # STEP 2: search DB only for relevant registered users
    known_users = search_similar_users(candidate_tokens)
    print(f'{known_users=}')


    chunks = split_file(path)
    results = []

    for chunk in chunks: # todo: parallelize this loop with threading.processor.pool
        result = agent.run_sync(json.dumps({
            "text": chunk.text,
            "known_users": known_users
        }))
        results.append({
            "chunk index": chunk.index,
            "chunk metadata": chunk.metadata,
            "analysis": result.output.model_dump(mode="json") ,
            "known_users": known_users
        })

    # response in JSON
    return Response(
        json.dumps(results, indent=2, ensure_ascii=False),
        mimetype="application/json"
    )


if __name__ == "__main__":
    app.run(port=5005)