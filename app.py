import os
import logging
from flask import Flask, render_template, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from extractor import extract_entities

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB max payload

# ---------------------------------------------------------------------------
# Rate limiting — prevent abuse on public endpoints
# ---------------------------------------------------------------------------
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "60 per hour"],
    storage_uri="memory://",
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
@limiter.limit("30 per minute")
def index():
    return render_template("index.html")


@app.route("/extract", methods=["POST"])
@limiter.limit("30 per minute")
def extract():
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("text"), str):
        return jsonify({"error": "Invalid request — JSON with 'text' key required"}), 400

    text = data["text"]
    source = data.get("source", "indeed")

    # Validate source to prevent unexpected input
    allowed_sources = {"indeed", "signalhire", "linkedin_xray", "linkedin_rps"}
    if source not in allowed_sources:
        return jsonify({"error": f"Invalid source. Must be one of: {', '.join(sorted(allowed_sources))}"}), 400

    if not text.strip():
        return jsonify({"error": "No text provided"}), 400

    # Cap input length to prevent regex abuse (ReDoS)
    if len(text) > 500_000:
        return jsonify({"error": "Input too long — max 500,000 characters"}), 400

    try:
        results = extract_entities(text, source=source)
    except Exception as exc:
        app.logger.exception("Extraction failed")
        return jsonify({"error": "Extraction failed. Please check your input."}), 500

    return jsonify(results)


@app.route("/health")
@limiter.exempt
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


@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"error": "Too many requests — please slow down"}), 429


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
