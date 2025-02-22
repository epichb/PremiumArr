import os
import logging
from flask import Flask, jsonify, request, render_template
from src.db import Database
from prometheus_client import generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST, Gauge, Info

CONFIG_PATH = os.getenv("CONFIG_PATH", "/config")

app = Flask(__name__)
app.config["DEBUG"] = False  # Flask debugging

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


@app.route("/metrics")
def metrics():
    try:
        registry = CollectorRegistry()

        total_entries = Gauge("total_entries", "Total number of entries in the database", registry=registry)
        done_entries = Gauge("done_entries", "Total number of done entries in the database", registry=registry)
        failed_entries = Gauge("failed_entries", "Total number of failed entries in the database", registry=registry)
        entries_by_state = Gauge("entries_by_state", "Number of entries by state", ["state"], registry=registry)
        retry_counts = Gauge("retry_counts", "Number of retries for operations", ["operation"], registry=registry)
        db_size_in_KB = Gauge("db_size_in_KB", "Size of the database file in KB", registry=registry)
        last_added_UTC = Info("last_added_UTC", "Timestamp of the last added entry", registry=registry)
        last_done_UTC = Info("last_done_UTC", "Timestamp of the last done entry", registry=registry)

        total_entries.set(db.get_total_entries_count())
        done_entries.set(db.get_done_entries_count())
        failed_entries.set(db.get_failed_entries_count())

        for state, count in db.get_entries_count_by_state().items():
            entries_by_state.labels(state=state).set(count)

        for operation, count in db.get_retry_counts().items():
            retry_counts.labels(operation=operation).set(count)
        db_size_in_KB.set(db.get_db_size_in_KB())
        last_added_UTC.info({"timestamp": str(db.get_last_added_timestamp())})
        last_done_UTC.info({"timestamp": str(db.get_last_done_timestamp())})

        data = generate_latest(registry)
        return data, 200, {"Content-Type": CONTENT_TYPE_LATEST}
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return "Error generating metrics", 500


@app.route("/api/logs")
def get_logs():
    try:
        LOG_FILE_PATH = os.path.join(CONFIG_PATH, "log", "for_webviewer.log")
        with open(LOG_FILE_PATH, "r") as log_file:
            log_file.seek(0, os.SEEK_END)
            log_size = log_file.tell()
            log_file.seek(max(log_size - 50000, 0), os.SEEK_SET)

            logs = log_file.readlines()
            lines = [line.encode("ascii", "ignore").decode() for line in logs]  # remove all non ASCII characters
            as_str = "".join(reversed(lines))

        return jsonify({"logs": as_str})
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return jsonify({"error": "Error fetching logs"}), 500


if __name__ == "__main__":
    if app.config["DEBUG"]:
        app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=True)
    else:
        app.run(host="0.0.0.0", port=5000, debug=False)
