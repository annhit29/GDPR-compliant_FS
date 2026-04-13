from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, Response #jsonify
from splitter import split_file
from agent import agent
import json
import threading
import time
import random

app = Flask(__name__)
_disabled = False

@app.post("/disable")
def disable():
    global _disabled
    _disabled = True
    return Response(json.dumps({"status": "disabled"}), mimetype="application/json")

@app.post("/enable")
def enable():
    global _disabled
    _disabled = False
    return Response(json.dumps({"status": "enabled"}), mimetype="application/json")

@app.post("/analyze-file")
def analyze_file():
    if _disabled:
        return Response(json.dumps([]), mimetype="application/json")

    data = request.json
    path = data["path"]
    known_users = data.get("known_users", []) # <- wanna scale up, so

    chunks = split_file(path)
    results = []

    def analyze_one(chunk):
        """Function executed inside each thread."""
        tid = threading.get_ident()
        print(f"[THREAD {tid}] START chunk {chunk.index}")
        start = time.time()

        result = agent.run_sync(json.dumps({
            "text": chunk.text,
            "known_users": known_users
        }))
        end = time.time()
        print(f"[THREAD {tid}] END chunk {chunk.index} took {end-start:.2f}s")

        return {
            "chunk index": chunk.index,
            "chunk metadata": chunk.metadata,
            "analysis": result.output.model_dump(mode="json")
        }
    

    # Limit pool size to control API rate (recommended: 16 or 32)
    if not chunks:
        return Response(json.dumps([], ensure_ascii=False), mimetype="application/json")
    MAX_WORKERS = min(32, len(chunks))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(analyze_one, chunk): chunk for chunk in chunks}

        for future in as_completed(futures):
            results.append(future.result())

    # Response to client
    return Response(
        json.dumps(results, indent=2, ensure_ascii=False),
        mimetype="application/json"
    )

if __name__ == "__main__":
    app.run(port=5005)