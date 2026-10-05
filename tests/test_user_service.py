"""
test_user_service.py — Unit Tests for Refactored user_service Module
=====================================================================
Validates security and performance refactoring:
- Bcrypt password hashing & verification
- SQL Injection immunity with parameterized queries
- Batch query resolution for N+1 database operations
- Environment variable enforcement for SECRET_KEY
"""

import os
import sqlite3
import pytest

from user_service import (
    get_secret_key,
    hash_password,
    verify_password,
    get_user,
    generate_monthly_report,
)


# ─────────────────────────────────────────────────────────────────────────────
# Pytest Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def in_memory_db():
    """
    Creates an isolated in-memory SQLite database pre-populated with test tables & data.
    """
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Seed test users
    users_data = [
        ("alice", hash_password("AlicePass2026!")),
        ("bob", hash_password("BobSecurePass#1")),
        ("charlie", hash_password("CharlieSecret@99")),
    ]
    cursor.executemany(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        users_data,
    )

    # Seed test usage records
    usage_data = [
        (1, "login", "2026-10-01 09:00:00"),
        (1, "view_dashboard", "2026-10-01 09:05:00"),
        (2, "login", "2026-10-02 11:15:00"),
        (2, "export_data", "2026-10-02 11:30:00"),
        (2, "logout", "2026-10-02 12:00:00"),
    ]
    cursor.executemany(
        "INSERT INTO usage (user_id, action, timestamp) VALUES (?, ?, ?)",
        usage_data,
    )

    conn.commit()
    yield conn
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Password Hashing & Verification Tests (Bcrypt)
# ─────────────────────────────────────────────────────────────────────────────

class TestPasswordSecurity:
    """Validates secure password handling using bcrypt."""

    def test_hash_password_produces_bcrypt_format(self):
        password = "SuperSecretPassword123!"
        hashed = hash_password(password)

        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert hashed != password

    def test_hash_password_uses_unique_salts(self):
        password = "IdenticalPassword!"
        hash_1 = hash_password(password)
        hash_2 = hash_password(password)

        # Same password hashed twice must produce distinct hashes due to salts
        assert hash_1 != hash_2

    def test_verify_password_success(self):
        password = "CorrectHorseBatteryStaple"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_wrong_password(self):
        password = "ValidPassword"
        hashed = hash_password(password)

        assert verify_password("WrongPasswordGuess", hashed) is False

    def test_verify_password_invalid_inputs(self):
        assert verify_password("", "some_hash") is False
        assert verify_password("pwd", "") is False
        assert verify_password("pwd", "not_a_bcrypt_hash") is False

    def test_hash_empty_password_raises_value_error(self):
        with pytest.raises(ValueError, match="Password cannot be empty"):
            hash_password("")


# ─────────────────────────────────────────────────────────────────────────────
# 2. SQL Injection Resistance Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSQLInjectionResistance:
    """Validates that get_user is fully immune to SQL Injection attacks."""

    def test_get_user_valid_existing_user(self, in_memory_db):
        user = get_user(in_memory_db, "alice")
        assert user is not None
        assert user[1] == "alice"

    def test_get_user_non_existent(self, in_memory_db):
        user = get_user(in_memory_db, "non_existent_user")
        assert user is None

    @pytest.mark.parametrize("payload", [
        "admin' OR '1'='1",
        "alice' OR '1'='1' --",
        "'; DROP TABLE users; --",
        "' UNION SELECT 1, 'hacked', 'pwned' --",
    ])
    def test_get_user_sql_injection_payloads_safely_rejected(self, in_memory_db, payload):
        """
        Verify that classic SQL Injection strings are treated strictly as literal username
        strings and do NOT bypass authentication or leak arbitrary rows.
        """
        result = get_user(in_memory_db, payload)
        assert result is None, f"SQL Injection payload '{payload}' succeeded unexpectedly!"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Batch Query / N+1 Resolution Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBatchReporting:
    """Validates generate_monthly_report batches requests and returns accurate stats."""

    def test_generate_monthly_report_multiple_users(self, in_memory_db):
        user_ids = [1, 2]
        report = generate_monthly_report(in_memory_db, user_ids)

        assert 1 in report
        assert 2 in report
        assert len(report[1]) == 2
        assert len(report[2]) == 3

        # Validate structure of records
        actions_user_1 = [rec["action"] for rec in report[1]]
        assert actions_user_1 == ["login", "view_dashboard"]

        actions_user_2 = [rec["action"] for rec in report[2]]
        assert actions_user_2 == ["login", "export_data", "logout"]

    def test_generate_monthly_report_user_with_no_usage(self, in_memory_db):
        # User 3 has no usage records
        report = generate_monthly_report(in_memory_db, [3])
        assert 3 in report
        assert report[3] == []

    def test_generate_monthly_report_empty_list(self, in_memory_db):
        report = generate_monthly_report(in_memory_db, [])
        assert report == {}

    def test_generate_monthly_report_large_user_list_chunking(self, in_memory_db):
        # Generate 1200 user IDs to verify chunking (>MAX_SQLITE_PARAMS)
        large_id_list = list(range(1, 1201))
        report = generate_monthly_report(in_memory_db, large_id_list)

        assert len(report) == 1200
        assert len(report[1]) == 2
        assert len(report[2]) == 3
        assert len(report[500]) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 4. Environment Variable Enforcement for SECRET_KEY
# ─────────────────────────────────────────────────────────────────────────────

class TestSecretKeyEnforcement:
    """Validates that APP_SECRET_KEY is strictly enforced from the environment."""

    def test_get_secret_key_success(self, monkeypatch):
        expected_key = "production_secure_token_987654321"
        monkeypatch.setenv("APP_SECRET_KEY", expected_key)

        assert get_secret_key() == expected_key

    def test_get_secret_key_raises_runtime_error_when_missing(self, monkeypatch):
        monkeypatch.delenv("APP_SECRET_KEY", raising=False)

        with pytest.raises(RuntimeError, match="APP_SECRET_KEY environment variable not set"):
            get_secret_key()

    def test_get_secret_key_raises_runtime_error_when_empty_or_whitespace(self, monkeypatch):
        monkeypatch.setenv("APP_SECRET_KEY", "   ")

        with pytest.raises(RuntimeError, match="APP_SECRET_KEY environment variable not set"):
            get_secret_key()
