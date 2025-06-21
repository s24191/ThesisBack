from fastapi_users.authentication import JWTStrategy, AuthenticationBackend, BearerTransport
import os

SECRET = os.getenv("JWT_SECRET")
if not SECRET:
    raise RuntimeError("backend:JWT_SECRET is not set in .env file.")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)
