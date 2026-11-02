import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .router import router as birds_router

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
token = os.getenv("TOKEN")

if token:
    os.environ["HF_TOKEN"] = token

Base.metadata.create_all(bind=engine)
app = FastAPI(title="AI Bird Lab")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(birds_router)