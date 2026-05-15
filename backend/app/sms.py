import africastalking
import os
from dotenv import load_dotenv

load_dotenv()

africastalking.initialize(
    username=os.getenv("AT_USERNAME"),
    api_key=os.getenv("AT_API_KEY")
)

sms = africastalking.SMS


def send_otp_sms(phone: str, otp: str):
    message = f"Goova - Votre code de connexion : {otp}\nValide 10 minutes."
    try:
        sms.send(message, [f"+222{phone}"])
    except Exception as e:
        print(f"OTP SMS non envoyé: {e}")


def send_booking_confirmation(phone: str, data: dict):
    message = f"""Goova ✅
Réservation confirmée !
Réf: {data['reference_code']}
Trajet: {data['from_city']} → {data['to_city']}
Date: {data['date']} à {data['time']}
Places: {data['seats']} | Total: {data['total_price']} MRU
Chauffeur: {data['driver_name']}
Tel chauffeur: {data['driver_phone']}
Paiement en espèces au départ."""
    try:
        sms.send(message, [f"+222{phone}"])
    except Exception as e:
        print(f"SMS non envoyé: {e}")


def send_cancellation(phone: str, reference: str):
    message = f"""Goova ❌
Réservation {reference} annulée.
Contactez-nous au besoin."""
    try:
        sms.send(message, [f"+222{phone}"])
    except Exception as e:
        print(f"SMS non envoyé: {e}")