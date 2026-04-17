from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/users", tags=["Utilisateurs"])


@router.post("/inscription", response_model=schemas.Token)
def inscription(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    # Vérifier si le numéro existe déjà
    existing = db.query(models.User).filter(
        models.User.phone == user_data.phone
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce numéro de téléphone est déjà utilisé"
        )

    # Créer l'utilisateur
    new_user = models.User(
        phone=user_data.phone,
        name=user_data.name,
        password_hash=hash_password(user_data.password),
        role=user_data.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Générer le token
    token = create_access_token(data={"sub": new_user.phone})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": new_user
    }


@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.phone == credentials.phone
    ).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Numéro ou mot de passe incorrect"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé, contactez l'administrateur"
        )

    token = create_access_token(data={"sub": user.phone})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@router.get("/moi", response_model=schemas.UserResponse)
def get_moi(current_user=Depends(get_current_user)):
    return current_user