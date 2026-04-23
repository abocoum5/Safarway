from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])


def check_admin(current_user):
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    total_users = db.query(models.User).count()
    total_chauffeurs = db.query(models.User).filter(models.User.role == models.UserRole.chauffeur).count()
    total_voyageurs = db.query(models.User).filter(models.User.role == models.UserRole.voyageur).count()
    total_trips = db.query(models.Trip).count()
    trips_actifs = db.query(models.Trip).filter(models.Trip.status == models.TripStatus.actif).count()
    total_bookings = db.query(models.Booking).count()
    bookings_confirmes = db.query(models.Booking).filter(models.Booking.status == models.BookingStatus.confirme).count()
    revenus = db.query(func.sum(models.Booking.commission)).filter(models.Booking.status == models.BookingStatus.confirme).scalar() or 0
    gmv = db.query(func.sum(models.Booking.total_price)).filter(models.Booking.status == models.BookingStatus.confirme).scalar() or 0

    return {
        "utilisateurs": {"total": total_users, "chauffeurs": total_chauffeurs, "voyageurs": total_voyageurs},
        "trajets": {"total": total_trips, "actifs": trips_actifs},
        "reservations": {"total": total_bookings, "confirmees": bookings_confirmes},
        "finances": {"commission_totale_MRU": round(revenus, 2), "volume_total_MRU": round(gmv, 2)}
    }


@router.get("/users", response_model=List[schemas.UserResponse])
def get_all_users(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    return db.query(models.User).order_by(models.User.id).all()


@router.patch("/users/{user_id}/activer")
def activer_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_active = True
    db.commit()
    return {"message": f"Utilisateur {user.name} activé"}


@router.patch("/users/{user_id}/desactiver")
def desactiver_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_active = False
    db.commit()
    return {"message": f"Utilisateur {user.name} désactivé"}


@router.delete("/users/{user_id}")
def supprimer_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.role == models.UserRole.admin:
        raise HTTPException(status_code=400, detail="Impossible de supprimer un admin")
    db.delete(user)
    db.commit()
    return {"message": f"Utilisateur {user.name} supprimé"}


@router.get("/trips", response_model=List[schemas.TripResponse])
def get_all_trips(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    trips = db.query(models.Trip).order_by(models.Trip.created_at.desc()).all()
    results = []
    for trip in trips:
        t = schemas.TripResponse.model_validate(trip)
        t.driver_name = trip.driver.name if trip.driver else None
        results.append(t)
    return results


@router.get("/bookings", response_model=List[schemas.BookingResponse])
def get_all_bookings(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    return db.query(models.Booking).order_by(models.Booking.created_at.desc()).all()