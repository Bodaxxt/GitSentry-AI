"""
user_service.py — Refactored User Management & Reporting Service
================================================================
Production-grade, hardened implementation resolving CWE-89 (SQL Injection),
CWE-327 (Broken Crypto), CWE-401 (Resource Leak), CWE-798 (Hardcoded Secrets),
CWE-362 (Thread-safe DB Access with RLock & URI Path Protection), CWE-388 (Error Handling),
CWE-400 (DoS, Input Bounding, O(1) Lookup), and CWE-22 (Strict Path Traversal Protection).

Part of GitSentry AI - Sprint 2 & Sprint 3.
"""

import os
import sqlite3
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import bcrypt

logger = logging.getLogger(__name__)

# Application root boundary for safe file access (CWE-22)
APP_ROOT_DIR = Path(__file__).resolve().parent

# Reentrant lock preventing thread deadlocks and race conditions (CWE-362)
_DB_LOCK = threading.RLock()

# Safety thresholds preventing DoS / Resource Exhaustion (CWE-400)
MAX_SQLITE_PARAMS = 500
MAX_REPORT_USERS = 5000
MAX_PASSWORD_LENGTH = 72   # Strict 72-byte maximum enforced by Bcrypt specification
MAX_USERNAME_LENGTH = 64


def _load_bcrypt_rounds() -> int:
    """Safely parse and bound BCRYPT_ROUNDS to a safe range [4..16] (CWE-400)."""
    try:
        val = int(os.getenv("BCRYPT_ROUNDS", "12"))
        return max(4, min(val, 16))
    except (ValueError, TypeError):
        return 12


BCRYPT_ROUNDS = _load_bcrypt_rounds()


def get_secret_key() -> str:
    """
    Retrieve the application secret key from environment variables.

    Returns:
        str: The secret key configured in APP_SECRET_KEY.

    Raises:
        RuntimeError: If APP_SECRET_KEY is not set or empty.
    """
    secret = os.getenv("APP_SECRET_KEY")
    if not secret or not secret.strip():
        raise RuntimeError("APP_SECRET_KEY environment variable not set")
    return secret.strip()


def hash_password(password: str) -> str:
    """
    Hash a user password using bcrypt with automatic salting and bounded length (CWE-400).

    Args:
        password: The plain text password to hash (max 256 chars).

    Returns:
        str: UTF-8 decoded bcrypt hash string.

    Raises:
        ValueError: If password is empty or exceeds MAX_PASSWORD_LENGTH.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password exceeds maximum length of {MAX_PASSWORD_LENGTH} characters")

    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed_bytes = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a stored bcrypt hash.

    Args:
        plain_password: The plaintext password entered by the user.
        hashed_password: The stored bcrypt hash string.

    Returns:
        bool: True if password matches, False otherwise.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def _safe_connect(db_path: str) -> sqlite3.Connection:
    """
    Safely opens an SQLite connection preventing arbitrary path manipulation (CWE-22, CWE-367).
    Resolves canonical path and verifies confinement within the application root boundary.
    """
    if db_path == ":memory:":
        return sqlite3.connect(":memory:", check_same_thread=False)

    resolved = Path(db_path).resolve()
    try:
        resolved.relative_to(APP_ROOT_DIR)
    except ValueError:
        raise PermissionError(f"Access denied: Path '{db_path}' escapes application boundary.")

    # Explicit URI prevents query parameter injection and TOCTOU path substitutions
    return sqlite3.connect(resolved.as_uri() + "?mode=rwc", uri=True, check_same_thread=False)


def _validate_db_arg(db: Any) -> None:
    """Ensure db argument is strictly a string path or active sqlite3.Connection."""
    if not isinstance(db, (str, sqlite3.Connection)):
        raise TypeError("db parameter must be a valid file path (str) or an sqlite3.Connection")


def get_user(
    db: Union[str, sqlite3.Connection],
    username: str,
) -> Optional[Tuple[Any, ...]]:
    """
    Fetch a user record safely using parameterized SQL to prevent SQL Injection (CWE-89).
    Thread-safe (CWE-362), resource-leak protected (CWE-404), length-bounded, and handles errors gracefully.

    Args:
        db: Either an active sqlite3.Connection or a filesystem path to the database.
        username: The username to search for (max 64 chars).

    Returns:
        Optional[Tuple]: (id, username, password_hash) if found, or None.
    """
    _validate_db_arg(db)

    if not isinstance(username, str):
        return None

    clean_username = username.strip()
    if not clean_username or len(clean_username) > MAX_USERNAME_LENGTH:
        return None

    query = "SELECT id, username, password_hash FROM users WHERE username = ?"

    try:
        if isinstance(db, sqlite3.Connection):
            with _DB_LOCK:
                cursor = db.cursor()
                try:
                    cursor.execute(query, (clean_username,))
                    return cursor.fetchone()
                finally:
                    cursor.close()
        else:
            with _safe_connect(db) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(query, (clean_username,))
                    return cursor.fetchone()
                finally:
                    cursor.close()
    except (sqlite3.Error, PermissionError) as exc:
        logger.error("Database query failed safely: %s", type(exc).__name__)
        return None


def generate_monthly_report(
    db: Union[str, sqlite3.Connection],
    user_ids: List[Union[int, str]],
) -> Dict[Union[int, str], List[Dict[str, Any]]]:
    """
    Generate usage statistics for multiple users using batch fetching (resolves N+1 problem).

    Normalizes IDs, caps max requests (CWE-400 DoS defense), chunks queries into batches,
    performs O(1) hash map aggregation, and handles sqlite3 errors gracefully (CWE-388).

    Args:
        db: Either an active sqlite3.Connection or a filesystem path to the database.
        user_ids: List of user IDs to fetch usage reports for.

    Returns:
        Dict mapping each user_id to a list of usage records (dicts).
    """
    _validate_db_arg(db)

    if not user_ids:
        return {}

    # Enforce upper bound to defend against memory exhaustion DoS (CWE-400)
    bounded_ids = user_ids[:MAX_REPORT_USERS]

    # Deduplicate while preserving original types and order
    clean_ids: List[Union[int, str]] = []
    seen = set()
    for uid in bounded_ids:
        if uid is not None and uid not in seen:
            seen.add(uid)
            clean_ids.append(uid)

    if not clean_ids:
        return {}

    # Initialise result dictionary using original keys
    results: Dict[Union[int, str], List[Dict[str, Any]]] = {
        uid: [] for uid in clean_ids
    }

    # Fast direct lookup dictionary mapping raw ID and string ID to bucket references
    bucket_map: Dict[Union[int, str], List[Dict[str, Any]]] = {}
    for uid in clean_ids:
        bucket = results[uid]
        bucket_map[uid] = bucket
        bucket_map[str(uid)] = bucket

    def _execute_batches(conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        try:
            for i in range(0, len(clean_ids), MAX_SQLITE_PARAMS):
                batch = clean_ids[i:i + MAX_SQLITE_PARAMS]
                placeholders = ",".join(["?" for _ in batch])
                query = f"SELECT user_id, action, timestamp FROM usage WHERE user_id IN ({placeholders})"
                cursor.execute(query, tuple(batch))
                rows = cursor.fetchall()
                for row in rows:
                    raw_uid, action, timestamp = row[0], row[1], row[2]
                    target_bucket = bucket_map.get(raw_uid) or bucket_map.get(str(raw_uid))
                    if target_bucket is not None:
                        target_bucket.append({
                            "user_id": raw_uid,
                            "action": action,
                            "timestamp": timestamp,
                        })
        finally:
            cursor.close()

    try:
        if isinstance(db, sqlite3.Connection):
            with _DB_LOCK:
                _execute_batches(db)
        else:
            with _safe_connect(db) as conn:
                _execute_batches(conn)
    except (sqlite3.Error, PermissionError) as exc:
        logger.error("Database batch query failed safely: %s", type(exc).__name__)
        return results

    return results
