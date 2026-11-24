from __future__ import annotations
import hashlib, hmac, os, secrets, time
from .models import User

class AuthError(Exception): pass

class AuthService:
    """Service 5/8: auth. PBKDF2-HMAC-SHA256 passwords, opaque bearer tokens (in-memory sessions).
    Production AWS mapping: Cognito user pools + JWT — tokens here are NOT JWTs, see README limitations."""
    def __init__(self, iterations: int = 60_000):
        self.users: dict[str, User] = {}
        self.by_email: dict[str, str] = {}
        self.tokens: dict[str, tuple[str, float]] = {}  # token -> (user_id, expiry)
        self.iterations = iterations

    def _hash(self, password: str, salt: bytes) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, self.iterations).hex()

    def register(self, email: str, password: str, role: str = "buyer") -> User:
        email = email.strip().lower()
        if "@" not in email: raise AuthError("invalid email")
        if len(password) < 8: raise AuthError("password must be >= 8 chars")
        if role not in {"buyer", "agent", "admin"}: raise AuthError("invalid role")
        if email in self.by_email: raise AuthError("email already registered")
        salt = os.urandom(16)
        user = User(id=f"u-{secrets.token_hex(6)}", email=email,
                    password_hash=f"{salt.hex()}${self._hash(password, salt)}", role=role)
        self.users[user.id] = user; self.by_email[email] = user.id
        return user

    def login(self, email: str, password: str, ttl: float = 3600) -> str:
        uid = self.by_email.get(email.strip().lower())
        if not uid: raise AuthError("invalid credentials")
        user = self.users[uid]
        salt_hex, expected = user.password_hash.split("$", 1)
        if not hmac.compare_digest(self._hash(password, bytes.fromhex(salt_hex)), expected):
            raise AuthError("invalid credentials")
        token = secrets.token_urlsafe(32)
        self.tokens[token] = (uid, time.time() + ttl)
        return token

    def authenticate(self, token: str) -> User:
        rec = self.tokens.get(token)
        if not rec: raise AuthError("invalid token")
        uid, exp = rec
        if time.time() > exp: self.tokens.pop(token, None); raise AuthError("token expired")
        return self.users[uid]

    def require_role(self, token: str, *roles: str) -> User:
        user = self.authenticate(token)
        if roles and user.role not in roles: raise AuthError(f"requires role {roles}")
        return user
