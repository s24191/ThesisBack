import uuid
from fastapi_users import FastAPIUsers
from shared.models.user import User
from shared.auth.manager import get_user_manager
from shared.auth.backend import auth_backend

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)
