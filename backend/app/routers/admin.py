from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text
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


@router.post("/users/{user_id}/reset-password")
def reset_user_password(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    from app.auth import hash_password
    import random, string
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.role == models.UserRole.admin:
        raise HTTPException(status_code=400, detail="Impossible de réinitialiser le mot de passe d'un admin")
    temp_password = "".join(random.choices(string.digits, k=6))
    user.password_hash = hash_password(temp_password)
    db.commit()
    return {"message": f"Mot de passe réinitialisé pour {user.name}", "temp_password": temp_password}


@router.post("/users/{user_id}/supprimer")
def supprimer_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    check_admin(current_user)
    row = db.execute(text("SELECT id, name, role FROM users WHERE id = :uid"), {"uid": user_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if row.role == "admin":
        raise HTTPException(status_code=400, detail="Impossible de supprimer un admin")
    name = row.name
    # Récupérer tous les IDs de trajets et réservations liés
    trip_ids = [r[0] for r in db.execute(text("SELECT id FROM trips WHERE driver_id = :uid"), {"uid": user_id}).fetchall()]
    trip_booking_ids = []
    if trip_ids:
        trip_booking_ids = [r[0] for r in db.execute(
            text("SELECT id FROM bookings WHERE trip_id = ANY(:ids)"), {"ids": trip_ids}
        ).fetchall()]
    pass_booking_ids = [r[0] for r in db.execute(
        text("SELECT id FROM bookings WHERE passenger_id = :uid"), {"uid": user_id}
    ).fetchall()]
    all_booking_ids = list(set(trip_booking_ids + pass_booking_ids))
    # Supprimer dans l'ordre des dépendances
    if all_booking_ids:
        db.execute(text("DELETE FROM reviews WHERE booking_id = ANY(:ids)"), {"ids": all_booking_ids})
    db.execute(text("DELETE FROM reviews WHERE passenger_id = :uid OR driver_id = :uid"), {"uid": user_id})
    if all_booking_ids:
        db.execute(text("DELETE FROM bookings WHERE id = ANY(:ids)"), {"ids": all_booking_ids})
    if trip_ids:
        db.execute(text("DELETE FROM trips WHERE id = ANY(:ids)"), {"ids": trip_ids})
    db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
    db.commit()
    return {"message": f"Utilisateur {name} supprimé"}


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


from pydantic import BaseModel as PydanticBaseModel

class SMSBroadcastRequest(PydanticBaseModel):
    message: str
    cible: str
    telephone: str = None


@router.post("/send-sms")
def envoyer_sms_broadcast(
    payload: SMSBroadcastRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    check_admin(current_user)
    from app.sms import _send_whatsapp

    if not payload.message or len(payload.message.strip()) < 2:
        raise HTTPException(status_code=400, detail="Message trop court")

    if payload.cible == "telephone":
        if not payload.telephone:
            raise HTTPException(status_code=400, detail="Numéro de téléphone requis")
        phone = payload.telephone.strip().replace("+222", "").replace(" ", "")
        try:
            _send_whatsapp(phone, payload.message)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        return {"envoyes": 1, "erreurs": 0}

    query = db.query(models.User).filter(models.User.is_active == True)
    if payload.cible == "chauffeurs":
        query = query.filter(models.User.role == models.UserRole.chauffeur)
    elif payload.cible == "voyageurs":
        query = query.filter(models.User.role == models.UserRole.voyageur)
    else:
        query = query.filter(models.User.role != models.UserRole.admin)

    users = query.all()
    envoyes, erreurs = 0, 0
    for u in users:
        try:
            _send_whatsapp(u.phone, payload.message)
            envoyes += 1
        except Exception as e:
            print(f"[WhatsApp broadcast] Erreur {u.phone}: {e}")
            erreurs += 1

    return {"envoyes": envoyes, "erreurs": erreurs, "total": len(users)}