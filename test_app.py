"""Tests for the Text Extractor application."""
import json
import pytest
from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def auth_client(client):
    """Create an authenticated test client."""
    with client.session_transaction() as sess:
        sess["user_email"] = "test@example.com"
    return client


# =========================================================================
# Route tests
# =========================================================================

class TestRoutes:
    def test_index_returns_html(self, auth_client):
        resp = auth_client.get("/")
        assert resp.status_code == 200
        assert b"DataExtractor" in resp.data

    def test_index_redirects_when_not_logged_in(self, client):
        resp = client.get("/")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "ok"

    def test_404_returns_json(self, client):
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert "error" in data

    def test_extract_requires_json(self, auth_client):
        resp = auth_client.post("/extract", data="not json")
        assert resp.status_code == 400

    def test_extract_requires_text_key(self, auth_client):
        resp = auth_client.post("/extract",
                           data=json.dumps({"wrong": "key"}),
                           content_type="application/json")
        assert resp.status_code == 400

    def test_extract_rejects_empty_text(self, auth_client):
        resp = auth_client.post("/extract",
                           data=json.dumps({"text": "   "}),
                           content_type="application/json")
        assert resp.status_code == 400

    def test_security_headers_present(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert "gleel2.com" in resp.headers.get("X-Frame-Options", "")


# =========================================================================
# Output structure tests (LLM-backed \u2014 requires CEREBRAS_API_KEY)
# =========================================================================

class TestOutputStructure:
    def test_response_has_all_keys(self, auth_client):
        text = """Test Person
Test Person
Dallas, TX
Relevant Work Experience
Manager
Company, 2023 - Present"""
        resp = auth_client.post("/extract",
                           data=json.dumps({"text": text}),
                           content_type="application/json")
        data = json.loads(resp.data)
        assert "names" in data
        assert "locations" in data
        assert "titles" in data
        assert "people" in data
        assert isinstance(data["names"], list)
        assert isinstance(data["locations"], list)
        assert isinstance(data["titles"], list)
        assert isinstance(data["people"], list)


# =========================================================================
# Auth route tests
# =========================================================================

class TestAuthRoutes:
    def test_login_page_accessible(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200

    def test_extract_requires_auth(self, client):
        resp = client.post("/extract",
                           data=json.dumps({"text": "test", "source": "indeed"}),
                           content_type="application/json")
        assert resp.status_code == 401

    def test_health_check_no_auth_needed(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_send_otp_requires_email(self, client):
        resp = client.post("/auth/send-otp",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 400

    def test_verify_otp_requires_fields(self, client):
        resp = client.post("/auth/verify-otp",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 400


# =========================================================================
# Access code route tests
# =========================================================================

class TestAccessCodeRoutes:
    def test_access_code_requires_otp_first(self, client):
        """Must verify OTP before access code step."""
        resp = client.post("/auth/verify-access-code",
                           data=json.dumps({"code": "1245"}),
                           content_type="application/json")
        assert resp.status_code == 401
        data = json.loads(resp.data)
        assert "OTP verification required" in data["error"]

    def test_access_code_requires_code_field(self, client):
        """Must provide a code in the request body."""
        with client.session_transaction() as sess:
            sess["otp_verified"] = True
            sess["pending_email"] = "test@example.com"
        resp = client.post("/auth/verify-access-code",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 400

    def test_valid_access_code_grants_access(self, client):
        """Correct code completes login."""
        with client.session_transaction() as sess:
            sess["otp_verified"] = True
            sess["pending_email"] = "test@example.com"
        resp = client.post("/auth/verify-access-code",
                           data=json.dumps({"code": "1245"}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["redirect"] == "/"
        # Session should now have user_email set
        with client.session_transaction() as sess:
            assert sess["user_email"] == "test@example.com"
            assert "otp_verified" not in sess

    def test_invalid_access_code_rejected(self, client):
        """Wrong code returns 401."""
        with client.session_transaction() as sess:
            sess["otp_verified"] = True
            sess["pending_email"] = "test@example.com"
        resp = client.post("/auth/verify-access-code",
                           data=json.dumps({"code": "0000"}),
                           content_type="application/json")
        assert resp.status_code == 401
        data = json.loads(resp.data)
        assert "Invalid access code" in data["error"]
