from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import engine, SessionLocal
from app import models
from app.routers import users, trips, bookings, admin, reviews
from app.routers import push

models.Base.metadata.create_all(bind=engine)


def run_migrations():
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS license_number VARCHAR"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS national_id_number VARCHAR"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS license_photo TEXT"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS national_id_photo TEXT"))
        conn.execute(text("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_approved BOOLEAN DEFAULT TRUE"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_phone_verified BOOLEAN DEFAULT TRUE"))
        conn.execute(text("ALTER TYPE tripstatus ADD VALUE IF NOT EXISTS 'termine'"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.commit()

run_migrations()

def _run_reminders():
    from app.reminders import send_daily_reminders
    send_daily_reminders(SessionLocal)

_scheduler = BackgroundScheduler(timezone="UTC")
_scheduler.add_job(_run_reminders, "cron", hour=7, minute=0)
_scheduler.start()

app = FastAPI(
    title="SafarWay API",
    description="Plateforme de transport interurbain en Mauritanie",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://safarway-roan.vercel.app",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(users.router)
app.include_router(trips.router)
app.include_router(bookings.router)
app.include_router(admin.router)
app.include_router(reviews.router)
app.include_router(push.router)

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