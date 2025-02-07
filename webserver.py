import os
import logging
from flask import Flask, jsonify, request, render_template
from src.db import Database
from prometheus_client import generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST, Gauge, Info

CONFIG_PATH = os.getenv("CONFIG_PATH", "/config")

app = Flask(__name__)
# app.config['DEBUG'] = True  # Enable Flask debugging

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
        last_added = Info("last_added", "Timestamp of the last added entry", registry=registry)
        last_done = Info("last_done", "Timestamp of the last done entry", registry=registry)

        total_entries.set(db.get_total_entries_count())
        done_entries.set(db.get_done_entries_count())
        failed_entries.set(db.get_failed_entries_count())

        for state, count in db.get_entries_count_by_state().items():
            entries_by_state.labels(state=state).set(count)

        for operation, count in db.get_retry_counts().items():
            retry_counts.labels(operation=operation).set(count)
        db_size_in_KB.set(db.get_db_size_in_KB())
        last_added.info({"timestamp": str(db.get_last_added_timestamp())})
        last_done.info({"timestamp": str(db.get_last_done_timestamp())})

        data = generate_latest(registry)
        return data, 200, {"Content-Type": CONTENT_TYPE_LATEST}
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return "Error generating metrics", 500


if __name__ == "__main__":
    # start Flask in a thread so it doesn't block the main process
    app.run(host="0.0.0.0", port=5000, debug=False)
