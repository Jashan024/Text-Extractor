"""Tests for auth module."""
import hashlib
import os
import pytest
from unittest.mock import patch, MagicMock
from auth import generate_otp, hash_otp


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
