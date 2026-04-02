"""Tests for auth module."""
import hashlib
import os
import pytest
from unittest.mock import patch, MagicMock
from auth import generate_otp, hash_otp, verify_access_code


class TestGenerateOTP:
    def test_returns_6_digit_string(self):
        otp = generate_otp()
        assert len(otp) == 6
        assert otp.isdigit()

    def test_returns_different_values(self):
        otps = {generate_otp() for _ in range(10)}
        assert len(otps) > 1  # not always the same


class TestHashOTP:
    def test_returns_sha256_hex(self):
        result = hash_otp("123456")
        expected = hashlib.sha256("123456".encode()).hexdigest()
        assert result == expected

    def test_different_input_different_hash(self):
        assert hash_otp("123456") != hash_otp("654321")


class TestVerifyAccessCode:
    def test_correct_code_returns_true(self):
        assert verify_access_code("1245") is True

    def test_wrong_code_returns_false(self):
        assert verify_access_code("0000") is False

    def test_empty_code_returns_false(self):
        assert verify_access_code("") is False

    def test_strips_whitespace(self):
        assert verify_access_code("  1245  ") is True

    @patch.dict(os.environ, {"ACCESS_CODE": "9999"})
    def test_respects_env_override(self):
        assert verify_access_code("9999") is True
        assert verify_access_code("1245") is False
