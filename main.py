from dotenv import load_dotenv


load_dotenv()
from contextlib import asynccontextmanager
from fastapi import FastAPI
from shared.auth.user_binding import fastapi_users, auth_backend
from shared.database import init_db
from shared.schemas.user import UserRead, UserCreate, UserUpdate
from fastapi.middleware.cors import CORSMiddleware
from features.wines.endpoints import router as wines_router
from features.wines.comments.wine_comments_endpoints import router as wine_comments_router
from features.wines.follows.wine_follows_endpoints import router as wine_follows_router
from features.wines.taste_votes.wine_taste_endpoints import router as wine_taste_router
from features.wines.notes.wine_notes_endpoints import router as wine_notes_router
from features.administration.lookups.endpoints import router as admin_router
from features.collection.workflow.endpoints import router as scraping_router
from features.administration.translation_reviews.endpoints import router as translation_router

import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
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
app.include_router(wines_router)
app.include_router(wine_comments_router)
app.include_router(wine_follows_router)
app.include_router(wine_taste_router)
app.include_router(wine_notes_router)
app.include_router(admin_router)
app.include_router(scraping_router)
app.include_router(translation_router)
@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
