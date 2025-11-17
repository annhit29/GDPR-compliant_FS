from flask import Flask, request, jsonify
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
        # 1. Run LLM → returns RAW JSON STRING
        result = agent.run_sync(json.dumps({ # call the gpt model
            "text": chunk.text,
            "known_users": known_users
        }))

        raw = result.output  # RAW JSON AS STRING FROM GPT

        # 2. Convert raw string → dict
        try:
            analysis_dict = json.loads(raw)
        except Exception as e:
            analysis_dict = {
                "error": "LLM returned invalid JSON",
                "raw_output": raw
            }

        # 3. Append to results
        results.append({
            "index": chunk.index,
            "metadata": chunk.metadata,
            "analysis": analysis_dict
        })

    return jsonify(results)

if __name__ == "__main__":
    app.run(port=5005)
