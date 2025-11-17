from flask import Flask, request, Response #jsonify
from splitter import split_file
from agent import agent
import json

app = Flask(__name__)

@app.post("/analyze-file")
def analyze_file():
    data = request.json
    path = data["path"]
    known_users = data.get("known_users", [])

    chunks = split_file(path)
    results = []

    for chunk in chunks:
        result = agent.run_sync(json.dumps({
            "text": chunk.text,
            "known_users": known_users
        }))
        results.append({
            "chunk index": chunk.index,
            "chunk metadata": chunk.metadata,
            "analysis": json.loads(result.output)   # convert to dict
        })

    # pretty-print JSON
    return Response(
        json.dumps(results, indent=2, ensure_ascii=False),
        mimetype="application/json"
    )


if __name__ == "__main__":
    app.run(port=5005)