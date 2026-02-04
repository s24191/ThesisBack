from dotenv import load_dotenv


load_dotenv()
from contextlib import asynccontextmanager
from fastapi import FastAPI
from shared.auth.user_binding import fastapi_users, auth_backend
from shared.database import init_db, seed_db_from_csv
from shared.schemas.user import UserRead, UserCreate, UserUpdate
from fastapi.middleware.cors import CORSMiddleware
from features.wines.endpoints import router as wines_router
from features.wines.list_dbo import router as wines_list_router
from features.wines.comments_endpoints import router as wine_comments_router

import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    if os.getenv("RUN_SEED", "false").lower() == "true":
        await seed_db_from_csv()

    yield

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
app.include_router(wines_list_router)

app.include_router(wines_router)
app.include_router(wine_comments_router)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
