from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

router = APIRouter(prefix="/trips", tags=["Trajets"])

VILLES = [
    "Nouakchott", "Nouadhibou", "Atar", "Kiffa",
    "Kaédi", "Néma", "Rosso", "Zouerate", "Tidjikja", "Aleg"
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
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    query = db.query(models.Trip).filter(
        models.Trip.status == models.TripStatus.actif,
        models.Trip.available_seats > 0
    )

    if from_city:
        query = query.filter(models.Trip.from_city == from_city)
    if to_city:
        query = query.filter(models.Trip.to_city == to_city)
    if date:
        query = query.filter(models.Trip.departure_date == date)

    trips = query.order_by(models.Trip.departure_date, models.Trip.departure_time).all()

    results = []
    for trip in trips:
        t = schemas.TripResponse.model_validate(trip)
        t.driver_name = trip.driver.name
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


@router.get("/villes/liste")
def get_villes():
    return {"villes": VILLES}