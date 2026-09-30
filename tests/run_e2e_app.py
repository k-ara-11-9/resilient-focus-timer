import os
import sys
from flask import send_from_directory

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app

# Serve frontend from dist
dist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory(os.path.join(dist_dir, "assets"), filename)

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_index(path):
    if os.path.exists(os.path.join(dist_dir, path)):
        return send_from_directory(dist_dir, path)
    return send_from_directory(dist_dir, "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("FLASK_RUN_PORT", 5005))
    app.run(port=port, debug=False)

