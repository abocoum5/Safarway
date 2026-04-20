from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import random
import string

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

router = APIRouter(prefix="/bookings", tags=["Réservations"])

COMMISSION_RATE = 10  # 10 MRU par place


def generate_reference():
    chars = string.ascii_uppercase + string.digits
    return "SW-" + "".join(random.choices(chars, k=8))


@router.post("/", response_model=schemas.BookingResponse)
def creer_reservation(
    booking_data: schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if current_user.role not in [models.UserRole.voyageur, models.UserRole.admin]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les voyageurs peuvent réserver"
        )

    trip = db.query(models.Trip).filter(
        models.Trip.id == booking_data.trip_id
    ).first()

    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable")

    if trip.status != models.TripStatus.actif:
        raise HTTPException(status_code=400, detail="Ce trajet n'est plus disponible")

    if trip.available_seats < booking_data.seats_booked:
        raise HTTPException(status_code=400, detail="Pas assez de places disponibles")

    if trip.driver_id == current_user.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas réserver votre propre trajet")

    total_price = trip.price_per_seat * booking_data.seats_booked
    commission = booking_data.seats_booked * COMMISSION_RATE

    reference = generate_reference()
    while db.query(models.Booking).filter(
        models.Booking.reference_code == reference
    ).first():
        reference = generate_reference()

    new_booking = models.Booking(
        trip_id=booking_data.trip_id,
        passenger_id=current_user.id,
        seats_booked=booking_data.seats_booked,
        total_price=total_price,
        commission=commission,
        reference_code=reference,
    )

    db.add(new_booking)

    trip.available_seats -= booking_data.seats_booked
    if trip.available_seats == 0:
        trip.status = models.TripStatus.complet

    db.commit()
    db.refresh(new_booking)

    # =========================
    # AJOUT DEMANDÉ (DRIVER INFO)
    # =========================
    new_booking.driver_phone = trip.driver.phone
    new_booking.driver_name = trip.driver.name

    # =========================
    # SMS CONFIRMATION
    # =========================
    try:
        from app.sms import send_booking_confirmation
        send_booking_confirmation(current_user.phone, {
            "reference_code": new_booking.reference_code,
            "from_city": trip.from_city,
            "to_city": trip.to_city,
            "date": trip.departure_date,
            "time": trip.departure_time,
            "seats": new_booking.seats_booked,
            "total_price": new_booking.total_price,
            "driver_phone": trip.driver.phone,
            "driver_name": trip.driver.name
        })
    except Exception as e:
        print(f"SMS non envoyé: {e}")


    return new_booking


@router.get("/mes-reservations", response_model=List[schemas.BookingResponse])
def mes_reservations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    bookings = db.query(models.Booking).filter(
        models.Booking.passenger_id == current_user.id
    ).order_by(models.Booking.created_at.desc()).all()

    # =========================
    # AJOUT DEMANDÉ
    # =========================
    for booking in bookings:
        booking.driver_phone = booking.trip.driver.phone
        booking.driver_name = booking.trip.driver.name

    return bookings


@router.get("/{booking_id}", response_model=schemas.BookingResponse)
def get_reservation(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    booking = db.query(models.Booking).filter(
        models.Booking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Réservation introuvable")

    if booking.passenger_id != current_user.id and current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Non autorisé")

    return booking


@router.patch("/{booking_id}/annuler", response_model=schemas.BookingResponse)
def annuler_reservation(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    booking = db.query(models.Booking).filter(
        models.Booking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Réservation introuvable")

    if booking.passenger_id != current_user.id and current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Non autorisé")

    if booking.status == models.BookingStatus.annule:
        raise HTTPException(status_code=400, detail="Déjà annulée")

    trip = db.query(models.Trip).filter(
        models.Trip.id == booking.trip_id
    ).first()

    trip.available_seats += booking.seats_booked
    if trip.status == models.TripStatus.complet:
        trip.status = models.TripStatus.actif

    booking.status = models.BookingStatus.annule

    db.commit()
    db.refresh(booking)

    try:
        from app.sms import send_cancellation
        send_cancellation(current_user.phone, booking.reference_code)
    except Exception as e:
        print(f"SMS non envoyé: {e}")

    return booking


@router.get("/trajet/{trip_id}", response_model=List[schemas.BookingResponse])
def reservations_du_trajet(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()

    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable")

    if trip.driver_id != current_user.id and current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Non autorisé")

    return db.query(models.Booking).filter(
        models.Booking.trip_id == trip_id
    ).all()