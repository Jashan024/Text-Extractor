"""Authentication module — OTP generation, hashing, Supabase + Resend integration."""
import hashlib
import os
import random
import string
from datetime import datetime, timezone, timedelta
from functools import wraps

import resend
from flask import session, redirect, url_for, request
from supabase import create_client

# ---------------------------------------------------------------------------
# Supabase client (lazy init)
# ---------------------------------------------------------------------------
_supabase = None


def get_supabase():
    global _supabase
    if _supabase is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
        _supabase = create_client(url, key)
    return _supabase


# ---------------------------------------------------------------------------
# OTP helpers
# ---------------------------------------------------------------------------
def generate_otp() -> str:
    """Generate a random 6-digit OTP."""
    return "".join(random.choices(string.digits, k=6))


def hash_otp(otp: str) -> str:
    """SHA-256 hash an OTP string."""
    return hashlib.sha256(otp.encode()).hexdigest()


# ---------------------------------------------------------------------------
# OTP lifecycle
# ---------------------------------------------------------------------------
OTP_TTL_MINUTES = 5


def store_otp(email: str, otp: str):
    """Hash and store OTP in Supabase. Invalidates previous unused OTPs."""
    sb = get_supabase()

    # Invalidate old unused OTPs for this email
    sb.table("otps").update({"used": True}).eq("email", email).eq("used", False).execute()

    # Store new OTP
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()
    sb.table("otps").insert({
        "email": email,
        "otp_hash": hash_otp(otp),
        "expires_at": expires_at,
    }).execute()


def verify_otp(email: str, otp: str) -> bool:
    """Verify OTP against Supabase. Returns True if valid."""
    sb = get_supabase()
    otp_hashed = hash_otp(otp)

    result = (
        sb.table("otps")
        .select("id, expires_at")
        .eq("email", email)
        .eq("otp_hash", otp_hashed)
        .eq("used", False)
        .execute()
    )

    if not result.data:
        return False

    record = result.data[0]
    expires_at = datetime.fromisoformat(record["expires_at"])

    if datetime.now(timezone.utc) > expires_at:
        return False

    # Mark as used
    sb.table("otps").update({"used": True}).eq("id", record["id"]).execute()

    # Upsert user
    sb.table("users").upsert({"email": email}, on_conflict="email").execute()

    return True


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------
def send_otp_email(email: str, otp: str):
    """Send OTP to user via Resend."""
    resend.api_key = os.environ.get("RESEND_API_KEY", "")

    resend.Emails.send({
        "from": os.environ.get("RESEND_FROM_EMAIL", "noreply@te.gleel2.com"),
        "to": [email],
        "subject": "Your login code for DataExtractor",
        "html": f"""
        <div style="font-family: 'Inter', sans-serif; max-width: 400px; margin: 0 auto; padding: 32px;">
            <h2 style="color: #4f46e5; margin-bottom: 8px;">DataExtractor</h2>
            <p style="color: #374151; font-size: 16px;">Your login code is:</p>
            <div style="background: #f0f2f5; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #1a1a2e;">{otp}</span>
            </div>
            <p style="color: #6b7280; font-size: 14px;">This code expires in 5 minutes. If you didn't request this, ignore this email.</p>
        </div>
        """,
    })


# ---------------------------------------------------------------------------
# Access code verification
# ---------------------------------------------------------------------------
def verify_access_code(code: str) -> bool:
    """Check the user-supplied access code against the configured value."""
    expected = os.environ.get("ACCESS_CODE", "1245")
    return code.strip() == expected


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------
def login_required(f):
    """Decorator to require authentication on a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_email" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function
