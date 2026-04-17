from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    voyageur = "voyageur"
    chauffeur = "chauffeur"
    admin = "admin"


class TripStatus(str, enum.Enum):
    actif = "actif"
    complet = "complet"
    annule = "annule"


class BookingStatus(str, enum.Enum):
    confirme = "confirme"
    annule = "annule"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.voyageur, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trips = relationship("Trip", back_populates="driver")
    bookings = relationship("Booking", back_populates="passenger")


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    from_city = Column(String, nullable=False)
    to_city = Column(String, nullable=False)
    departure_date = Column(String, nullable=False)
    departure_time = Column(String, nullable=False)
    total_seats = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
    price_per_seat = Column(Float, nullable=False)
    vehicle_type = Column(String, nullable=False)
    status = Column(Enum(TripStatus), default=TripStatus.actif)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    driver = relationship("User", back_populates="trips")
    bookings = relationship("Booking", back_populates="trip")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    seats_booked = Column(Integer, nullable=False)
    total_price = Column(Float, nullable=False)
    commission = Column(Float, nullable=False)
    status = Column(Enum(BookingStatus), default=BookingStatus.confirme)
    reference_code = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip = relationship("Trip", back_populates="bookings")
    passenger = relationship("User", back_populates="bookings")
