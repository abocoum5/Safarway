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

@router.post("/inscription", response_model=schemas.Token)
def inscription(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.phone == user_data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ce numéro est déjà utilisé")

    if not user_data.password or len(user_data.password) < 6:
        raise HTTPException(status_code=400, detail="Mot de passe obligatoire (6 caractères minimum)")

    if user_data.role == models.UserRole.chauffeur:
        if not user_data.name:
            raise HTTPException(status_code=400, detail="Nom obligatoire pour les chauffeurs")

    new_user = models.User(
        name=user_data.name or ("Voyageur " + user_data.phone[-4:]),
        phone=user_data.phone,
        password_hash=hash_password(user_data.password),
        role=user_data.role,
        is_phone_verified=True,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if new_user.role == models.UserRole.chauffeur:
        try:
            from app.sms import send_whatsapp_admin
            send_whatsapp_admin(
                f"Goova - Nouveau chauffeur inscrit !\n"
                f"Nom : {new_user.name}\n"
                f"Tel : {new_user.phone}\n"
                f"Approuvez-le depuis le panel admin."
            )
        except Exception as e:
            print(f"[WhatsApp notif] {e}")

    token = create_access_token({"sub": str(new_user.id)})
    return {"access_token": token, "token_type": "bearer", "user": new_user}


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
        print(f"[ADMIN OTP] {email} → {otp}")
    except Exception as e:
        print(f"[ADMIN OTP FALLBACK] Email non envoyé ({e}). Code pour {email} : {otp}")

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

    if not user:
        raise HTTPException(status_code=404, detail="Numéro introuvable. Créez d'abord un compte.")
    if user.role == models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Utilisez la connexion admin par email")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    otp = generate_otp()
    user.otp_code = otp
    user.otp_expires = datetime.utcnow() + timedelta(minutes=10)
    db.commit()

    try:
        send_otp_sms(phone, otp)
    except Exception as e:
        print(f"OTP SMS non envoyé: {e}")

    return {"message": "Code envoyé"}


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
# SETUP PREMIER ADMIN (utilisable une seule fois)
# ─────────────────────────────────────────────

@router.get("/admin/who")
def who_is_admin(db: Session = Depends(get_db)):
    admin = db.query(models.User).filter(models.User.role == models.UserRole.admin).first()
    if not admin:
        return {"admin": None, "message": "Aucun admin trouvé"}
    email = admin.email or ""
    masked = (email[:2] + "***" + email[email.find("@"):]) if "@" in email else "(pas d'email)"
    return {"admin_name": admin.name, "admin_email_masked": masked, "has_email": bool(admin.email)}


@router.get("/admin/setup")
def setup_admin(email: str, phone: str, name: str, password: str, db: Session = Depends(get_db)):
    existing_admin = db.query(models.User).filter(models.User.role == models.UserRole.admin).first()
    if existing_admin:
        raise HTTPException(status_code=403, detail="Un admin existe déjà. Endpoint désactivé.")

    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    admin = models.User(
        phone=phone,
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=models.UserRole.admin,
        is_active=True,
        is_approved=True,
        is_phone_verified=True,
    )
    db.add(admin)
    db.commit()
    print(f"[ADMIN SETUP] Compte admin créé : {email}")
    return {"message": "Admin créé. Connectez-vous avec votre email et mot de passe.", "email": email}


@router.post("/admin/login")
def admin_login(email: str, password: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.email == email,
        models.User.role == models.UserRole.admin
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


# ─────────────────────────────────────────────
# PROFIL
# ─────────────────────────────────────────────

@router.post("/reset-password/request")
def reset_password_request(phone: str, db: Session = Depends(get_db)):
    from app.email_service import generate_otp
    from app.sms import send_otp_sms

    user = db.query(models.User).filter(models.User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Numéro introuvable")
    if user.role == models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Réinitialisation non autorisée pour les admins")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    otp = generate_otp()
    user.otp_code = otp
    user.otp_expires = datetime.utcnow() + timedelta(minutes=10)
    db.commit()

    try:
        send_otp_sms(phone, otp)
    except Exception as e:
        print(f"OTP reset SMS non envoyé: {e}")

    return {"message": "Code de vérification envoyé par SMS"}


@router.post("/reset-password")
def reset_password(phone: str, otp: str, new_password: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Numéro introuvable")
    if user.role == models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Réinitialisation non autorisée pour les admins")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")
    if not user.otp_code or user.otp_code != otp:
        raise HTTPException(status_code=400, detail="Code incorrect")
    if not user.otp_expires or datetime.utcnow() > user.otp_expires:
        raise HTTPException(status_code=400, detail="Code expiré, demandez-en un nouveau")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Mot de passe : 6 caractères minimum")

    user.password_hash = hash_password(new_password)
    user.otp_code = None
    user.otp_expires = None
    db.commit()
    return {"message": "Mot de passe réinitialisé"}


@router.get("/moi", response_model=schemas.UserResponse)
def mon_profil(current_user=Depends(get_current_user)):
    return current_user


@router.post("/moi/documents")
def soumettre_documents(doc: schemas.UserDocumentSubmit, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != models.UserRole.chauffeur:
        raise HTTPException(status_code=403, detail="Réservé aux chauffeurs")
    if not doc.license_number or not doc.national_id_number:
        raise HTTPException(status_code=400, detail="N° permis et N° carte d'identité obligatoires")
    current_user.license_number = doc.license_number.strip()
    current_user.national_id_number = doc.national_id_number.strip()
    if doc.license_photo:
        current_user.license_photo = doc.license_photo
    if doc.national_id_photo:
        current_user.national_id_photo = doc.national_id_photo
    db.commit()
    try:
        from app.sms import send_whatsapp_admin
        send_whatsapp_admin(
            f"Goova - Dossier chauffeur soumis !\n"
            f"Nom : {current_user.name}\n"
            f"Tel : {current_user.phone}\n"
            f"Permis : {current_user.license_number}\n"
            f"CIN : {current_user.national_id_number}\n"
            f"Approuvez-le depuis le panel admin."
        )
    except Exception as e:
        print(f"[WhatsApp dossier] {e}")
    return {"message": "Dossier soumis, en attente de validation"}


@router.get("/{user_id}/profil")
def get_driver_profil(user_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import func as sqlfunc
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or user.role != models.UserRole.chauffeur:
        raise HTTPException(status_code=404, detail="Profil chauffeur introuvable")

    avg = db.query(sqlfunc.avg(models.Review.rating)).filter(models.Review.driver_id == user_id).scalar()
    total_reviews = db.query(models.Review).filter(models.Review.driver_id == user_id).count()
    total_trips = db.query(models.Trip).filter(models.Trip.driver_id == user_id).count()

    reviews = (
        db.query(models.Review)
        .filter(models.Review.driver_id == user_id)
        .order_by(models.Review.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "id": user.id,
        "name": user.name,
        "member_since": user.created_at.strftime("%B %Y") if user.created_at else None,
        "total_trips": total_trips,
        "average_rating": round(float(avg), 1) if avg else None,
        "total_reviews": total_reviews,
        "reviews": [
            {
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at.strftime("%d/%m/%Y") if r.created_at else None,
            }
            for r in reviews
        ],
    }


@router.patch("/moi", response_model=schemas.UserResponse)
def update_profil(user_update: schemas.UserUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if user_update.name:
        current_user.name = user_update.name.strip()
    if user_update.new_password:
        if not user_update.current_password:
            raise HTTPException(status_code=400, detail="Mot de passe actuel requis")
        if not verify_password(user_update.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
        if len(user_update.new_password) < 6:
            raise HTTPException(status_code=400, detail="Nouveau mot de passe : 6 caractères minimum")
        current_user.password_hash = hash_password(user_update.new_password)
    db.commit()
    db.refresh(current_user)
    return current_user