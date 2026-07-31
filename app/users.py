"""
User account management.
Stores users in a local JSON file with salted+hashed passwords. Each user
gets their own knowledge base, chat history, and uploaded files — namespaced
by username so multiple people can use the same RAGent instance separately.
"""

import os
import json
import hashlib
import secrets
from dotenv import load_dotenv

load_dotenv()

USERS_PATH = "data/users.json"
os.makedirs("data", exist_ok=True)


def _load_users():
    if os.path.exists(USERS_PATH):
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_users(users):
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _ensure_default_admin():
    """Seeds a default admin user from .env on first run, for backward compatibility."""
    users = _load_users()
    if not users:
        default_user = os.environ.get("APP_USERNAME", "admin")
        default_pass = os.environ.get("APP_PASSWORD", "ragent123")
        salt = secrets.token_hex(8)
        users[default_user] = {"salt": salt, "hash": _hash_password(default_pass, salt)}
        _save_users(users)
    return users


def create_user(username: str, password: str) -> tuple:
    """Returns (success: bool, message: str)."""
    username = username.strip()
    if not username or not password:
        return False, "Username and password cannot be empty."

    users = _ensure_default_admin()
    if username in users:
        return False, "That username is already taken."

    salt = secrets.token_hex(8)
    users[username] = {"salt": salt, "hash": _hash_password(password, salt)}
    _save_users(users)

    os.makedirs(f"vectorstore/{username}", exist_ok=True)
    os.makedirs(f"data/uploaded_docs/{username}", exist_ok=True)
    return True, "Account created."


def verify_user(username: str, password: str) -> bool:
    users = _ensure_default_admin()
    user = users.get(username.strip())
    if not user:
        return False
    return _hash_password(password, user["salt"]) == user["hash"]


def user_exists(username: str) -> bool:
    users = _ensure_default_admin()
    return username.strip() in users
