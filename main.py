from dotenv import load_dotenv


load_dotenv()
from contextlib import asynccontextmanager
from fastapi import FastAPI
from shared.auth.user_binding import fastapi_users, auth_backend
from shared.database import init_db
from features.users.register.endpoint import router as register_router
from features.users.login.endpoint import router as login_router
from shared.schemas.user import UserRead, UserCreate, UserUpdate
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan():
    await init_db()
    yield
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_users_router(
        user_schema=UserRead,
        user_update_schema=UserUpdate,
    ),
    prefix="/auth/users",
    tags=["users"],
)

app.include_router(register_router)
app.include_router(login_router)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
