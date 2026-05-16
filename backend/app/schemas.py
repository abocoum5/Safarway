from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models import UserRole, TripStatus, BookingStatus


# ─── USER SCHEMAS ───────────────────────────────────────────

class UserCreate(BaseModel):
    phone: str
    name: Optional[str] = None
    password: Optional[str] = None
    role: UserRole = UserRole.voyageur
    license_number: Optional[str] = None
    national_id_number: Optional[str] = None
    license_photo: Optional[str] = None
    national_id_photo: Optional[str] = None


class UserLogin(BaseModel):
    phone: str
    password: str


class UserResponse(BaseModel):
    id: int
    phone: str
    name: str
    role: UserRole
    is_active: bool
    is_approved: Optional[bool] = None
    created_at: datetime
    license_number: Optional[str] = None
    national_id_number: Optional[str] = None

    class Config:
        from_attributes = True


class UserDocuments(BaseModel):
    license_photo: Optional[str] = None
    national_id_photo: Optional[str] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


# ─── TRIP SCHEMAS ───────────────────────────────────────────

class TripCreate(BaseModel):
    from_city: str
    to_city: str
    departure_date: str
    departure_time: str
    total_seats: int
    price_per_seat: float
    vehicle_type: str


class TripResponse(BaseModel):
    id: int
    driver_id: int
    from_city: str
    to_city: str
    departure_date: str
    departure_time: str
    total_seats: int
    available_seats: int
    price_per_seat: float
    vehicle_type: str
    status: TripStatus
    created_at: datetime
    driver_name: Optional[str] = None

    class Config:
        from_attributes = True


# ─── BOOKING SCHEMAS ────────────────────────────────────────

class BookingCreate(BaseModel):
    trip_id: int
    seats_booked: int


class BookingResponse(BaseModel):
    id: int
    trip_id: int
    passenger_id: int
    seats_booked: int
    total_price: float
    commission: float
    status: BookingStatus
    reference_code: str
    created_at: datetime

    # ✅ AJOUTS DEMANDÉS
    driver_phone: Optional[str] = None
    driver_name: Optional[str] = None

    class Config:
        from_attributes = True