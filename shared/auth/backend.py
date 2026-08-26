from fastapi_users.authentication import JWTStrategy, AuthenticationBackend, BearerTransport
import os

SECRET = os.getenv("JWT_SECRET")
if not SECRET:
    raise RuntimeError("backend:JWT_SECRET is not set in .env file.")

JWT_LIFETIME_SECONDS = int(
    os.getenv(
        "JWT_LIFETIME_SECONDS",
        str(60 * 60 * 24 * 7),
    )
)

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=JWT_LIFETIME_SECONDS)

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)
