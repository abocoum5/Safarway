import africastalking
import os
from dotenv import load_dotenv

load_dotenv()

africastalking.initialize(
    username=os.getenv("AT_USERNAME"),
    api_key=os.getenv("AT_API_KEY")
)

sms = africastalking.SMS

def send_booking_confirmation(phone: str, booking_data: dict):
    message = f"""SafarWay ✅
Réservation confirmée !
Réf: {booking_data['reference_code']}
Trajet: {booking_data['from_city']} → {booking_data['to_city']}
Date: {booking_data['date']} à {booking_data['time']}
Places: {booking_data['seats']} | Total: {booking_data['total_price']} MRU
Paiement en espèces au chauffeur."""

    try:
        sms.send(message, [f"+222{phone}"])
    except Exception as e:
        print(f"SMS non envoyé: {e}")

def send_cancellation(phone: str, reference: str):
    message = f"""SafarWay ❌
Réservation {reference} annulée.
Contactez-nous au besoin."""
    try:
        sms.send(message, [f"+222{phone}"])
    except Exception as e:
        print(f"SMS non envoyé: {e}")