from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user, create_access_token, verify_password, get_password_hash

router = APIRouter(prefix="/users", tags=["Utilisateurs"])


# ─────────────────────────────────────────────
# INSCRIPTION
# ─────────────────────────────────────────────

@router.post("/inscription", response_model=schemas.LoginResponse)
def inscription(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.phone == user_data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ce numéro est déjà utilisé")

    hashed = get_password_hash(user_data.password)
    new_user = models.User(
        name=user_data.name,
        phone=user_data.phone,
        password_hash=hashed,
        role=user_data.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": str(new_user.id)})
    return {"access_token": token, "user": new_user}


# ─────────────────────────────────────────────
# CONNEXION NORMALE (téléphone + mot de passe)
# ─────────────────────────────────────────────

@router.post("/login", response_model=schemas.LoginResponse)
def login(credentials: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone == credentials.phone).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Numéro ou mot de passe incorrect")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    if user.role == models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Les admins doivent se connecter par email")

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "user": user}


# ─────────────────────────────────────────────
# CONNEXION ADMIN — Étape 1 : demander OTP
# ─────────────────────────────────────────────

@router.post("/admin/request-otp")
def admin_request_otp(email: str, db: Session = Depends(get_db)):
    from app.email_service import generate_otp, send_otp_email

    user = db.query(models.User).filter(
        models.User.email == email,
        models.User.role == models.UserRole.admin
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Email admin introuvable")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    otp = generate_otp()
    user.otp_code = otp
    user.otp_expires = datetime.utcnow() + timedelta(minutes=10)
    db.commit()

    try:
        send_otp_email(email, otp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur envoi email: {e}")

    return {"message": "Code envoyé par email"}


# ─────────────────────────────────────────────
# CONNEXION ADMIN — Étape 2 : vérifier OTP
# ─────────────────────────────────────────────

@router.post("/admin/verify-otp", response_model=schemas.LoginResponse)
def admin_verify_otp(email: str, otp: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.email == email,
        models.User.role == models.UserRole.admin
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Email admin introuvable")

    if not user.otp_code or user.otp_code != otp:
        raise HTTPException(status_code=400, detail="Code incorrect")

    if not user.otp_expires or datetime.utcnow() > user.otp_expires:
        raise HTTPException(status_code=400, detail="Code expiré, demandez-en un nouveau")

    user.otp_code = None
    user.otp_expires = None
    db.commit()

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "user": user}


# ─────────────────────────────────────────────
# PROFIL
# ─────────────────────────────────────────────

@router.get("/moi", response_model=schemas.UserResponse)
def mon_profil(current_user=Depends(get_current_user)):
    return current_user