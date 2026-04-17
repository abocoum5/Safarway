from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import random
import string
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

router = APIRouter(prefix="/bookings", tags=["Réservations"])

COMMISSION_RATE = 0.07  # 7% de commission


def generate_reference():
    chars = string.ascii_uppercase + string.digits
    return "SW-" + "".join(random.choices(chars, k=8))


@router.post("/", response_model=schemas.BookingResponse)
def creer_reservation(
    booking_data: schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Seuls les voyageurs peuvent réserver
    if current_user.role not in [models.UserRole.voyageur, models.UserRole.admin]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les voyageurs peuvent réserver"
        )

    # Vérifier que le trajet existe
    trip = db.query(models.Trip).filter(
        models.Trip.id == booking_data.trip_id
    ).first()

    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable")

    # Vérifier que le trajet est actif
    if trip.status != models.TripStatus.actif:
        raise HTTPException(
            status_code=400,
            detail="Ce trajet n'est plus disponible"
        )

    # Vérifier les places disponibles
    if trip.available_seats < booking_data.seats_booked:
        raise HTTPException(
            status_code=400,
            detail=f"Pas assez de places. Disponibles: {trip.available_seats}"
        )

    # Vérifier que le voyageur ne réserve pas son propre trajet
    if trip.driver_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Vous ne pouvez pas réserver votre propre trajet"
        )

    # Calculer le prix et la commission
    total_price = trip.price_per_seat * booking_data.seats_booked
    commission = total_price * COMMISSION_RATE

    # Générer un code de référence unique
    reference = generate_reference()
    while db.query(models.Booking).filter(
        models.Booking.reference_code == reference
    ).first():
        reference = generate_reference()

    # Créer la réservation
    new_booking = models.Booking(
        trip_id=booking_data.trip_id,
        passenger_id=current_user.id,
        seats_booked=booking_data.seats_booked,
        total_price=total_price,
        commission=commission,
        reference_code=reference,
    )
    db.add(new_booking)

    # Mettre à jour les places disponibles
    trip.available_seats -= booking_data.seats_booked

    # Si plus de places, marquer le trajet comme complet
    if trip.available_seats == 0:
        trip.status = models.TripStatus.complet

    db.commit()
    db.refresh(new_booking)

    return new_booking


@router.get("/mes-reservations", response_model=List[schemas.BookingResponse])
def mes_reservations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    bookings = db.query(models.Booking).filter(
        models.Booking.passenger_id == current_user.id
    ).order_by(models.Booking.created_at.desc()).all()
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

    # Seul le passager ou l'admin peut voir la réservation
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
        raise HTTPException(status_code=400, detail="Réservation déjà annulée")

    # Remettre les places disponibles
    trip = db.query(models.Trip).filter(
        models.Trip.id == booking.trip_id
    ).first()

    trip.available_seats += booking.seats_booked
    if trip.status == models.TripStatus.complet:
        trip.status = models.TripStatus.actif

    booking.status = models.BookingStatus.annule
    db.commit()
    db.refresh(booking)

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

    bookings = db.query(models.Booking).filter(
        models.Booking.trip_id == trip_id
    ).all()
    return bookings