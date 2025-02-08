import os
import logging
from flask import Flask, jsonify, request, render_template
from src.db import Database
from src.sabnzbd_api import SabnzbdApi

CONFIG_PATH = os.getenv("CONFIG_PATH", "/config")

app = Flask(__name__)
# app.config['DEBUG'] = True  # Enable Flask debugging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

db = Database(CONFIG_PATH)

sabnzbd = SabnzbdApi()


@app.route("/")
def index():
    try:
        res = render_template("index.html")
    except Exception as e:
        logger.error(f"Error rendering template: {e}")
        res = "Error rendering template"
    return res


@app.route("/api", methods=["GET"])
def api():
    if request.args.get("mode"):
        mode = request.args.get("mode")
        if mode == "version":
            return sabnzbd.get_version()
        if mode == "get_config":
            return sabnzbd.get_config()
        if mode == "queue":
            return sabnzbd.get_queue()
        if mode == "history":
            return sabnzbd.get_history()
        return {"error": "Invalid mode"}
    return jsonify({"error": "No mode specified"})


@app.route("/api", methods=["POST"])
def api_post():
    # Handle the mode "addfile" here
    # We expect a multipart/form-data request with a file
    # The field containing the file should be named "name" of "nzbfile"
    if request.args.get("mode") == "addfile":
        data = request.files.get("nzbfile")
        if not data:
            data = request.files.get("name")
        if data:
            return sabnzbd.add_file(data)
        return {"error": "No file provided"}


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
