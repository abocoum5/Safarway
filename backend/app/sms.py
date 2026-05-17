import vonage
import os
from dotenv import load_dotenv

load_dotenv()

client = vonage.Client(
    key=os.getenv("VONAGE_API_KEY"),
    secret=os.getenv("VONAGE_API_SECRET")
)
sms = vonage.Sms(client)


def _send(phone: str, message: str):
    to = f"222{phone}"
    response = sms.send_message({
        "from": "Goova",
        "to": to,
        "text": message,
    })
    msg = response["messages"][0]
    print(f"[SMS] to={to} status={msg['status']} remaining-balance={msg.get('remaining-balance')} error={msg.get('error-text')}")
    if msg["status"] != "0":
        raise Exception(msg["error-text"])


def send_otp_sms(phone: str, otp: str):
    try:
        _send(phone, f"Goova - Votre code de connexion : {otp}\nValide 10 minutes.")
    except Exception as e:
        print(f"OTP SMS non envoyé: {e}")


def send_booking_confirmation(phone: str, data: dict):
    message = (
        f"Goova ✅ Réservation confirmée !\n"
        f"Réf: {data['reference_code']}\n"
        f"Trajet: {data['from_city']} → {data['to_city']}\n"
        f"Date: {data['date']} à {data['time']}\n"
        f"Places: {data['seats']} | Total: {data['total_price']} MRU\n"
        f"Chauffeur: {data['driver_name']} — {data['driver_phone']}\n"
        f"Paiement en espèces au départ."
    )
    try:
        _send(phone, message)
    except Exception as e:
        print(f"SMS confirmation non envoyé: {e}")


def send_trip_reminder_passenger(phone: str, data: dict):
    message = (
        f"Goova ⏰ Rappel trajet demain !\n"
        f"{data['from_city']} → {data['to_city']}\n"
        f"Le {data['date']} à {data['time']}\n"
        f"Réf: {data['reference']}\n"
        f"Chauffeur: {data['driver_name']} — {data['driver_phone']}"
    )
    try:
        _send(phone, message)
    except Exception as e:
        print(f"SMS rappel passager non envoyé: {e}")


def send_trip_reminder_driver(phone: str, data: dict):
    message = (
        f"Goova ⏰ Rappel chauffeur demain !\n"
        f"{data['from_city']} → {data['to_city']}\n"
        f"Le {data['date']} à {data['time']}\n"
        f"{data['passengers']} passager(s) vous attendent."
    )
    try:
        _send(phone, message)
    except Exception as e:
        print(f"SMS rappel chauffeur non envoyé: {e}")


def send_cancellation(phone: str, reference: str):
    try:
        _send(phone, f"Goova ❌ Réservation {reference} annulée.\nContactez-nous au besoin.")
    except Exception as e:
        print(f"SMS annulation non envoyé: {e}")
