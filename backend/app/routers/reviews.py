from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import date
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

router = APIRouter(prefix="/reviews", tags=["Avis"])


@router.post("/", response_model=schemas.ReviewResponse)
def create_review(
    review_data: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    booking = db.query(models.Booking).filter(
        models.Booking.id == review_data.booking_id,
        models.Booking.passenger_id == current_user.id,
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    if booking.status != models.BookingStatus.confirme:
        raise HTTPException(status_code=400, detail="Réservation non confirmée")
    if not booking.trip:
        raise HTTPException(status_code=400, detail="Trajet introuvable")
    if booking.trip.departure_date >= date.today().strftime("%Y-%m-%d"):
        raise HTTPException(status_code=400, detail="Vous pouvez noter uniquement après le trajet")

    existing = db.query(models.Review).filter(models.Review.booking_id == review_data.booking_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vous avez déjà noté ce trajet")

    if not 1 <= review_data.rating <= 5:
        raise HTTPException(status_code=400, detail="Note entre 1 et 5")

    review = models.Review(
        booking_id=review_data.booking_id,
        passenger_id=current_user.id,
        driver_id=booking.trip.driver_id,
        rating=review_data.rating,
        comment=review_data.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.get("/chauffeur/{driver_id}")
def get_driver_reviews(driver_id: int, db: Session = Depends(get_db)):
    reviews = (
        db.query(models.Review)
        .filter(models.Review.driver_id == driver_id)
        .order_by(models.Review.created_at.desc())
        .all()
    )
    avg = db.query(func.avg(models.Review.rating)).filter(
        models.Review.driver_id == driver_id
    ).scalar()
    return {
        "driver_id": driver_id,
        "average_rating": round(float(avg), 1) if avg else None,
        "total_reviews": len(reviews),
        "reviews": [schemas.ReviewResponse.model_validate(r) for r in reviews],
    }
