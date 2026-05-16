from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from app import models


def send_daily_reminders(db_factory):
    db = db_factory()
    count = {"passengers": 0, "drivers": 0}
    try:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        bookings = (
            db.query(models.Booking)
            .options(
                joinedload(models.Booking.trip).joinedload(models.Trip.driver),
                joinedload(models.Booking.passenger),
            )
            .join(models.Trip)
            .filter(
                models.Trip.departure_date == tomorrow,
                models.Booking.status == models.BookingStatus.confirme,
                models.Trip.status == models.TripStatus.actif,
            )
            .all()
        )

        notified_passengers: set = set()
        notified_drivers: set = set()

        for booking in bookings:
            trip = booking.trip
            if not trip:
                continue
            passenger = booking.passenger
            driver = trip.driver

            if passenger and passenger.phone not in notified_passengers:
                from app.sms import send_trip_reminder_passenger
                send_trip_reminder_passenger(passenger.phone, {
                    "from_city": trip.from_city,
                    "to_city": trip.to_city,
                    "date": trip.departure_date,
                    "time": trip.departure_time,
                    "reference": booking.reference_code,
                    "driver_name": driver.name if driver else "—",
                    "driver_phone": driver.phone if driver else "—",
                })
                notified_passengers.add(passenger.phone)
                count["passengers"] += 1

            if driver and driver.phone not in notified_drivers:
                confirmed_seats = sum(
                    1 for b in trip.bookings
                    if b.status == models.BookingStatus.confirme
                )
                from app.sms import send_trip_reminder_driver
                send_trip_reminder_driver(driver.phone, {
                    "from_city": trip.from_city,
                    "to_city": trip.to_city,
                    "date": trip.departure_date,
                    "time": trip.departure_time,
                    "passengers": confirmed_seats,
                })
                notified_drivers.add(driver.phone)
                count["drivers"] += 1

        print(f"[Reminders] {count['passengers']} passagers, {count['drivers']} chauffeurs notifiés pour le {tomorrow}")
        return count

    except Exception as e:
        print(f"[Reminders] Erreur: {e}")
        return count
    finally:
        db.close()
