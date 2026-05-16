from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user, create_access_token, verify_password, hash_password

router = APIRouter(prefix="/users", tags=["Utilisateurs"])


# ─────────────────────────────────────────────
# INSCRIPTION
# ─────────────────────────────────────────────

@router.post("/inscription")
def inscription(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    from app.email_service import generate_otp
    from app.sms import send_otp_sms

    existing = db.query(models.User).filter(models.User.phone == user_data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ce numéro est déjà utilisé")

    if user_data.role == models.UserRole.chauffeur:
        if not user_data.name:
            raise HTTPException(status_code=400, detail="Nom obligatoire pour les chauffeurs")
        if not user_data.license_number or not user_data.national_id_number:
            raise HTTPException(status_code=400, detail="Numéro de permis et d'identité obligatoires pour les chauffeurs")
        if not user_data.license_photo or not user_data.national_id_photo:
            raise HTTPException(status_code=400, detail="Photos du permis et de la carte d'identité obligatoires pour les chauffeurs")

    hashed = hash_password(user_data.password) if user_data.password else None
    otp = generate_otp()
    new_user = models.User(
        name=user_data.name or ("Voyageur " + user_data.phone[-4:]),
        phone=user_data.phone,
        password_hash=hashed,
        role=user_data.role,
        license_number=user_data.license_number,
        national_id_number=user_data.national_id_number,
        license_photo=user_data.license_photo,
        national_id_photo=user_data.national_id_photo,
        otp_code=otp,
        otp_expires=datetime.utcnow() + timedelta(minutes=10),
        is_phone_verified=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    try:
        send_otp_sms(new_user.phone, otp)
    except Exception as e:
        print(f"OTP inscription non envoyé: {e}")

    return {"pending_verification": True, "phone": new_user.phone}


@router.post("/verify-inscription", response_model=schemas.Token)
def verify_inscription(phone: str, otp: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Numéro introuvable")
    if not user.otp_code or user.otp_code != otp:
        raise HTTPException(status_code=400, detail="Code incorrect")
    if not user.otp_expires or datetime.utcnow() > user.otp_expires:
        raise HTTPException(status_code=400, detail="Code expiré")

    user.otp_code = None
    user.otp_expires = None
    user.is_phone_verified = True
    db.commit()

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


# ─────────────────────────────────────────────
# CONNEXION NORMALE (téléphone + mot de passe)
# ─────────────────────────────────────────────

@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone == credentials.phone).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Numéro ou mot de passe incorrect")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    if user.role == models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Les admins doivent se connecter par email")

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


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

@router.post("/admin/verify-otp", response_model=schemas.Token)
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
    return {"access_token": token, "token_type": "bearer", "user": user}


# ─────────────────────────────────────────────
# CONNEXION PAR SMS OTP (voyageurs & chauffeurs)
# ─────────────────────────────────────────────

@router.post("/phone-otp/request")
def request_phone_otp(phone: str, db: Session = Depends(get_db)):
    from app.email_service import generate_otp
    from app.sms import send_otp_sms

    user = db.query(models.User).filter(models.User.phone == phone).first()

    if user:
        if user.role == models.UserRole.admin:
            raise HTTPException(status_code=403, detail="Utilisez la connexion admin par email")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Compte désactivé")
    else:
        user = models.User(
            phone=phone,
            name="Voyageur " + phone[-4:],
            password_hash=None,
            role=models.UserRole.voyageur,
            is_active=True,
        )
        db.add(user)
        db.flush()

    otp = generate_otp()
    user.otp_code = otp
    user.otp_expires = datetime.utcnow() + timedelta(minutes=10)
    db.commit()

    try:
        send_otp_sms(phone, otp)
    except Exception as e:
        print(f"OTP SMS non envoyé: {e}")

    return {"message": "Code envoyé par SMS"}


@router.post("/phone-otp/verify", response_model=schemas.Token)
def verify_phone_otp(phone: str, otp: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone == phone).first()

    if not user:
        raise HTTPException(status_code=404, detail="Numéro introuvable")
    if not user.otp_code or user.otp_code != otp:
        raise HTTPException(status_code=400, detail="Code incorrect")
    if not user.otp_expires or datetime.utcnow() > user.otp_expires:
        raise HTTPException(status_code=400, detail="Code expiré")

    user.otp_code = None
    user.otp_expires = None
    db.commit()

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


# ─────────────────────────────────────────────
# PROFIL
# ─────────────────────────────────────────────

@router.get("/moi", response_model=schemas.UserResponse)
def mon_profil(current_user=Depends(get_current_user)):
    return current_user