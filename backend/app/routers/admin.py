from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import get_current_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    total_users = db.query(models.User).count()
    total_chauffeurs = db.query(models.User).filter(
        models.User.role == models.UserRole.chauffeur
    ).count()
    total_voyageurs = db.query(models.User).filter(
        models.User.role == models.UserRole.voyageur
    ).count()
    total_trips = db.query(models.Trip).count()
    trips_actifs = db.query(models.Trip).filter(
        models.Trip.status == models.TripStatus.actif
    ).count()
    total_bookings = db.query(models.Booking).count()
    bookings_confirmes = db.query(models.Booking).filter(
        models.Booking.status == models.BookingStatus.confirme
    ).count()

    # Revenus totaux (commission)
    revenus = db.query(
        func.sum(models.Booking.commission)
    ).filter(
        models.Booking.status == models.BookingStatus.confirme
    ).scalar() or 0

    # Volume total de transactions
    gmv = db.query(
        func.sum(models.Booking.total_price)
    ).filter(
        models.Booking.status == models.BookingStatus.confirme
    ).scalar() or 0

    return {
        "utilisateurs": {
            "total": total_users,
            "chauffeurs": total_chauffeurs,
            "voyageurs": total_voyageurs
        },
        "trajets": {
            "total": total_trips,
            "actifs": trips_actifs
        },
        "reservations": {
            "total": total_bookings,
            "confirmees": bookings_confirmes
        },
        "finances": {
            "commission_totale_MRU": round(revenus, 2),
            "volume_total_MRU": round(gmv, 2)
        }
    }


@router.get("/users", response_model=List[schemas.UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()


@router.patch("/users/{user_id}/activer")
def activer_user(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_active = True
    db.commit()
    return {"message": f"Utilisateur {user.name} activé"}


@router.patch("/users/{user_id}/desactiver")
def desactiver_user(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_active = False
    db.commit()
    return {"message": f"Utilisateur {user.name} désactivé"}


@router.get("/trips", response_model=List[schemas.TripResponse])
def get_all_trips(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    trips = db.query(models.Trip).order_by(models.Trip.created_at.desc()).all()
    results = []
    for trip in trips:
        t = schemas.TripResponse.model_validate(trip)
        t.driver_name = trip.driver.name
        results.append(t)
    return results


@router.get("/bookings", response_model=List[schemas.BookingResponse])
def get_all_bookings(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    return db.query(models.Booking).order_by(
        models.Booking.created_at.desc()
    ).all()


@router.post("/users/creer-admin")
def creer_admin(
    user_data: schemas.UserCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    from app.auth import hash_password
    existing = db.query(models.User).filter(
        models.User.phone == user_data.phone
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ce numéro est déjà utilisé")

    admin = models.User(
        phone=user_data.phone,
        name=user_data.name,
        password_hash=hash_password(user_data.password),
        role=models.UserRole.admin
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return {"message": f"Admin {admin.name} créé avec succès"}