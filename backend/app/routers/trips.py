from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import date
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

router = APIRouter(prefix="/trips", tags=["Trajets"])

VILLES = [
    "Nouakchott", "Nouadhibou", "Rosso", "Kaédi", "Kiffa", "Néma",
    "Ayoun el Atrous", "Atar", "Tidjikja", "Sélibaby", "Zouerate",
    "Akjoujt", "Aleg", "Boghé", "Boutilimit", "Timbedra", "Bassikounou",
    "Oualata", "Chinguetti", "Ouadane", "Fdérik", "Bir Moghrein",
    "Kayes", "Monguel", "Maghama", "M'Bout", "Guerou", "Kankossa",
    "Barkéol", "Moudjeria", "Ould Yengé", "Ghabou", "Diaguily",
    "Mederdra", "Tekane", "R'Kiz", "Keur Macène",
    "Amourj", "Djiguenni", "Kobenni", "Tamchakett", "Tintane",
    "Boumdeid", "Tichitt", "Aoujeft", "Choum",
    "Adel Bagrou", "Bababe", "Bir Gandouz", "Benichab", "El Ain",
    "Terjit", "Aghreijit", "Rachid", "Nbeika", "Hassi Cheggar",
    "Dakar",
]


@router.post("/", response_model=schemas.TripResponse)
def publier_trajet(
    trip_data: schemas.TripCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Seuls les chauffeurs peuvent publier
    if current_user.role not in [models.UserRole.chauffeur, models.UserRole.admin]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les chauffeurs peuvent publier des trajets"
        )

    if current_user.role == models.UserRole.chauffeur and not current_user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte chauffeur est en attente de validation par un administrateur"
        )

    # Valider les villes
    if trip_data.from_city not in VILLES or trip_data.to_city not in VILLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Villes invalides. Villes disponibles: {', '.join(VILLES)}"
        )

    if trip_data.from_city == trip_data.to_city:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La ville de départ et d'arrivée doivent être différentes"
        )

    new_trip = models.Trip(
        driver_id=current_user.id,
        from_city=trip_data.from_city,
        to_city=trip_data.to_city,
        departure_date=trip_data.departure_date,
        departure_time=trip_data.departure_time,
        total_seats=trip_data.total_seats,
        available_seats=trip_data.total_seats,
        price_per_seat=trip_data.price_per_seat,
        vehicle_type=trip_data.vehicle_type,
    )
    db.add(new_trip)
    db.commit()
    db.refresh(new_trip)

    # Ajouter le nom du chauffeur
    result = schemas.TripResponse.model_validate(new_trip)
    result.driver_name = current_user.name
    return result


@router.get("/", response_model=List[schemas.TripResponse])
def rechercher_trajets(
    from_city: Optional[str] = Query(None, description="Ville de départ"),
    to_city: Optional[str] = Query(None, description="Ville d'arrivée"),
    date_filter: Optional[str] = Query(None, description="Date (YYYY-MM-DD)", alias="date"),
    db: Session = Depends(get_db)
):
    today = date.today().strftime("%Y-%m-%d")
    query = db.query(models.Trip).filter(
        models.Trip.status == models.TripStatus.actif,
        models.Trip.available_seats > 0,
        models.Trip.departure_date >= today
    )

    if from_city:
        query = query.filter(models.Trip.from_city == from_city)
    if to_city:
        query = query.filter(models.Trip.to_city == to_city)
    if date_filter:
        query = query.filter(models.Trip.departure_date == date_filter)

    trips = query.order_by(models.Trip.departure_date, models.Trip.departure_time).all()

    driver_ids = list({trip.driver_id for trip in trips})
    ratings = {
        row[0]: round(float(row[1]), 1)
        for row in db.query(models.Review.driver_id, func.avg(models.Review.rating))
        .filter(models.Review.driver_id.in_(driver_ids))
        .group_by(models.Review.driver_id)
        .all()
    } if driver_ids else {}

    results = []
    for trip in trips:
        t = schemas.TripResponse.model_validate(trip)
        t.driver_name = trip.driver.name
        t.driver_rating = ratings.get(trip.driver_id)
        results.append(t)

    return results


@router.get("/mes-trajets", response_model=List[schemas.TripResponse])
def mes_trajets(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    trips = db.query(models.Trip).filter(
        models.Trip.driver_id == current_user.id
    ).order_by(models.Trip.created_at.desc()).all()

    results = []
    for trip in trips:
        t = schemas.TripResponse.model_validate(trip)
        t.driver_name = current_user.name
        results.append(t)

    return results


@router.get("/{trip_id}", response_model=schemas.TripResponse)
def get_trajet(trip_id: int, db: Session = Depends(get_db)):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trajet introuvable"
        )
    result = schemas.TripResponse.model_validate(trip)
    result.driver_name = trip.driver.name
    avg = db.query(func.avg(models.Review.rating)).filter(
        models.Review.driver_id == trip.driver_id
    ).scalar()
    result.driver_rating = round(float(avg), 1) if avg else None
    return result


@router.patch("/{trip_id}/statut")
def changer_statut(
    trip_id: int,
    statut: models.TripStatus,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable")

    if trip.driver_id != current_user.id and current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Non autorisé")

    trip.status = statut
    db.commit()
    return {"message": f"Statut mis à jour: {statut}"}


@router.patch("/{trip_id}/annuler")
def annuler_trajet(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    trip = db.query(models.Trip).options(joinedload(models.Trip.driver)).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable")
    if trip.driver_id != current_user.id and current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Non autorisé")
    if trip.status in [models.TripStatus.annule, models.TripStatus.termine]:
        raise HTTPException(status_code=400, detail="Trajet déjà annulé ou terminé")

    confirmed_bookings = (
        db.query(models.Booking)
        .options(joinedload(models.Booking.passenger))
        .filter(
            models.Booking.trip_id == trip_id,
            models.Booking.status == models.BookingStatus.confirme
        )
        .all()
    )

    for b in confirmed_bookings:
        b.status = models.BookingStatus.annule

    trip.status = models.TripStatus.annule
    db.commit()

    for b in confirmed_bookings:
        if b.passenger:
            try:
                from app.sms import _send
                _send(b.passenger.phone,
                    f"Goova - Trajet annulé !\n"
                    f"{trip.from_city} > {trip.to_city} le {trip.departure_date}\n"
                    f"Votre réservation {b.reference_code} est annulée par le chauffeur."
                )
            except Exception as e:
                print(f"[SMS annulation chauffeur] {e}")
            try:
                from app.push import send_push_to_user
                send_push_to_user(db, b.passenger_id, {
                    "title": "Trajet annulé",
                    "body": f"{trip.from_city} → {trip.to_city} le {trip.departure_date} a été annulé par le chauffeur",
                })
            except Exception as e:
                print(f"[Push annulation] {e}")

    return {"message": f"Trajet annulé. {len(confirmed_bookings)} passager(s) notifié(s)."}


@router.patch("/{trip_id}/terminer")
def terminer_trajet(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable")
    if trip.driver_id != current_user.id and current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Non autorisé")
    if trip.status == models.TripStatus.annule:
        raise HTTPException(status_code=400, detail="Trajet annulé")
    if trip.status == models.TripStatus.termine:
        raise HTTPException(status_code=400, detail="Trajet déjà terminé")

    trip.status = models.TripStatus.termine
    db.commit()

    confirmed_bookings = (
        db.query(models.Booking)
        .filter(
            models.Booking.trip_id == trip_id,
            models.Booking.status == models.BookingStatus.confirme
        )
        .all()
    )

    for b in confirmed_bookings:
        try:
            from app.push import send_push_to_user
            send_push_to_user(db, b.passenger_id, {
                "title": "Trajet terminé !",
                "body": f"Comment était votre trajet {trip.from_city} → {trip.to_city} ? Laissez un avis.",
            })
        except Exception as e:
            print(f"[Push terminer] {e}")

    return {"message": "Trajet marqué comme terminé"}


@router.get("/villes/liste")
def get_villes():
    return {"villes": VILLES}