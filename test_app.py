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

    def test_extract_rejects_invalid_source(self, auth_client):
        resp = auth_client.post("/extract",
                           data=json.dumps({"text": "hello", "source": "badvalue"}),
                           content_type="application/json")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "Invalid source" in data["error"]

    def test_security_headers_present(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"


# =========================================================================
# Indeed parser tests
# =========================================================================

class TestIndeedParser:
    def test_single_profile(self, auth_client):
        text = """John Smith
John Smith
Philadelphia, PA
Relevant Work Experience
Registered Nurse
Penn Medicine, 2020 - Present
Education
Bachelor of Science"""
        resp = auth_client.post("/extract",
                           data=json.dumps({"text": text, "source": "indeed"}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["people"]) == 1
        assert data["people"][0]["name"] == "John Smith"
        assert data["people"][0]["location"] == "Philadelphia, PA"
        assert "Registered Nurse" in data["people"][0]["titles"]

    def test_multiple_profiles(self, auth_client):
        text = """Alice Johnson
Alice Johnson
New York, NY
Relevant Work Experience
Software Engineer
Google, 2021 - Present

Bob Williams
Bob Williams
Austin, TX
Relevant Work Experience
Data Analyst
Meta, 2019 - 2023"""
        resp = auth_client.post("/extract",
                           data=json.dumps({"text": text, "source": "indeed"}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["people"]) == 2
        assert data["people"][0]["name"] == "Alice Johnson"
        assert data["people"][1]["name"] == "Bob Williams"

    def test_no_profiles_returns_empty(self, auth_client):
        text = "random text with no structure at all 12345"
        resp = auth_client.post("/extract",
                           data=json.dumps({"text": text, "source": "indeed"}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["people"]) == 0

    def test_profile_without_duplicate_name(self, auth_client):
        text = """Jane Doe
Miami, FL
Relevant Work Experience
Project Manager
IBM, 2022 - Present"""
        resp = auth_client.post("/extract",
                           data=json.dumps({"text": text, "source": "indeed"}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["people"]) == 1
        assert data["people"][0]["name"] == "Jane Doe"
        assert data["people"][0]["location"] == "Miami, FL"


# =========================================================================
# SignalHire parser tests
# =========================================================================

class TestSignalHireParser:
    def test_single_profile(self, auth_client):
        text = """* S
Susan Grimes
Watched
Dentist at
__Shelburne Village Dentistry__
Shelburne, Vermont, United States
37 years exp"""
        resp = auth_client.post("/extract",
                           data=json.dumps({"text": text, "source": "signalhire"}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["people"]) == 1
        assert data["people"][0]["name"] == "Susan Grimes"
        assert "Dentist" in data["people"][0]["titles"]


# =========================================================================
# LinkedIn X-ray parser tests
# =========================================================================

class TestLinkedInXrayParser:
    def test_single_profile(self, auth_client):
        text = """Dana Ellis - Registered Nurse at Penn Medicine
LinkedIn \u00b7 Dana Ellis
90+ followers
Burlington, Vermont, United States \u00b7 Registered Nurse \u00b7 Penn Medicine"""
        resp = auth_client.post("/extract",
                           data=json.dumps({"text": text, "source": "linkedin_xray"}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["people"]) == 1
        assert data["people"][0]["name"] == "Dana Ellis"


# =========================================================================
# LinkedIn RPS parser tests
# =========================================================================

class TestLinkedInRPSParser:
    def test_single_profile(self, auth_client):
        text = """1. Select John Smith, DDS
John Smith
Third degree connection\u00b7 3rd
General Dentist at Main Street Dental
Burlington, Vermont, United States
\u00b7 Dentists"""
        resp = auth_client.post("/extract",
                           data=json.dumps({"text": text, "source": "linkedin_rps"}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["people"]) == 1
        assert "John Smith" in data["people"][0]["name"]


# =========================================================================
# Output structure tests
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
