import os
import logging
from flask import Flask, render_template, request, jsonify

from extractor import extract_entities

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB max payload

# Production logging
if not app.debug:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/extract", methods=["POST"])
def extract():
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("text"), str):
        return jsonify({"error": "Invalid request — JSON with 'text' key required"}), 400

    text = data["text"]
    if not text.strip():
        return jsonify({"error": "No text provided"}), 400

    try:
        results = extract_entities(text)
    except Exception as exc:
        app.logger.exception("Extraction failed")
        return jsonify({"error": "Extraction failed. Please check your input."}), 500

    return jsonify(results)


@app.route("/health")
def health():
    """Health-check endpoint for monitoring / load balancers."""
    return jsonify({"status": "ok"}), 200


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "Payload too large — 2 MB max"}), 413


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
