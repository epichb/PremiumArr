import os
import logging
from flask import Flask, jsonify, request, render_template
from src.db import Database

CONFIG_PATH = os.getenv("CONFIG_PATH", "/config")

app = Flask(__name__)
#app.config['DEBUG'] = True  # Enable Flask debugging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

db = Database(CONFIG_PATH)

@app.route("/")
def index():
    try:
        res = render_template("index.html")
    except Exception as e:
        logger.error(f"Error rendering template: {e}")
        res = "Error rendering template"
    return res

@app.route("/api/current_state")
def current_state():
    try:
        data = db.get_current_state()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error fetching current state: {e}")
        return jsonify({"error": "Error fetching current state"}), 500

@app.route("/api/done_failed")
def done_failed():
    try:
        limit = int(request.args.get("limit", 10))
        offset = int(request.args.get("offset", 0))
        data = db.get_done_failed_entries(limit=limit, offset=offset)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error fetching done/failed entries: {e}")
        return jsonify({"error": "Error fetching done/failed entries"}), 500

if __name__ == "__main__":
    # start Flask in a thread so it doesn't block the main process
    app.run(host="0.0.0.0", port=5000, debug=False)
