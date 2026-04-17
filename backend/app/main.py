from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine
from app import models
from app.routers import users, trips, bookings, admin

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SafarWay API",
    description="Plateforme de transport interurbain en Mauritanie",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(trips.router)
app.include_router(bookings.router)
app.include_router(admin.router)

@app.get("/")
def root():
    return {
        "message": "SafarWay API - Bienvenue",
        "version": "1.0.0",
        "status": "en ligne"
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}