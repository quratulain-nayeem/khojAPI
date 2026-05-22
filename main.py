from fastapi import FastAPI
from contextlib import asynccontextmanager
from db.database import engine, Base
from api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="khojAPI",
    description="Local Business Intelligence Agent for Indian Markets",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(router)