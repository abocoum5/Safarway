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


@router.get("/stats/hebdo")
def get_stats_hebdo(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    bookings = db.query(models.Booking).filter(
        models.Booking.status == models.BookingStatus.confirme
    ).all()
    by_week: dict = {}
    for b in bookings:
        if not b.created_at:
            continue
        week = b.created_at.strftime("%Y-W%W")
        if week not in by_week:
            by_week[week] = {"commission": 0.0, "gmv": 0.0, "count": 0}
        by_week[week]["commission"] += b.commission
        by_week[week]["gmv"] += b.total_price
        by_week[week]["count"] += 1
    sorted_weeks = sorted(by_week.keys())[-12:]
    return {
        "labels": sorted_weeks,
        "commissions": [round(by_week[w]["commission"], 2) for w in sorted_weeks],
        "gmv": [round(by_week[w]["gmv"], 2) for w in sorted_weeks],
        "counts": [by_week[w]["count"] for w in sorted_weeks],
    }


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


@router.get("/users/{user_id}/documents", response_model=schemas.UserDocuments)
def get_user_documents(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return user


@router.patch("/users/{user_id}/approuver")
def approuver_chauffeur(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.role != models.UserRole.chauffeur:
        raise HTTPException(status_code=400, detail="Cet utilisateur n'est pas un chauffeur")
    user.is_approved = True
    db.commit()
    return {"message": f"Chauffeur {user.name} approuvé"}


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
    # Supprimer les avis écrits par cet utilisateur
    db.query(models.Review).filter(models.Review.passenger_id == user_id).delete(synchronize_session=False)
    # Supprimer les avis reçus par cet utilisateur (chauffeur)
    db.query(models.Review).filter(models.Review.driver_id == user_id).delete(synchronize_session=False)
    # Supprimer les avis liés aux réservations de ses trajets
    trip_ids = [t.id for t in user.trips]
    if trip_ids:
        booking_ids = [b.id for b in db.query(models.Booking).filter(models.Booking.trip_id.in_(trip_ids)).all()]
        if booking_ids:
            db.query(models.Review).filter(models.Review.booking_id.in_(booking_ids)).delete(synchronize_session=False)
        db.query(models.Booking).filter(models.Booking.trip_id.in_(trip_ids)).delete(synchronize_session=False)
    db.query(models.Trip).filter(models.Trip.driver_id == user_id).delete(synchronize_session=False)
    # Supprimer les avis liés aux réservations du passager
    passenger_booking_ids = [b.id for b in db.query(models.Booking).filter(models.Booking.passenger_id == user_id).all()]
    if passenger_booking_ids:
        db.query(models.Review).filter(models.Review.booking_id.in_(passenger_booking_ids)).delete(synchronize_session=False)
    db.query(models.Booking).filter(models.Booking.passenger_id == user_id).delete(synchronize_session=False)
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


@router.post("/send-reminders")
def envoyer_rappels(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    from app.database import SessionLocal
    from app.reminders import send_daily_reminders
    count = send_daily_reminders(SessionLocal)
    return {"message": "Rappels envoyés", "passagers": count["passengers"], "chauffeurs": count["drivers"]}