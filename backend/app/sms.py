import vonage
import os
import subprocess
import urllib.request
import urllib.parse
import json
from dotenv import load_dotenv

load_dotenv()


def _send_whatsapp_meta(phone: str, message: str):
    """Envoie un message WhatsApp via Meta Cloud API."""
    phone_number_id = os.getenv("META_PHONE_NUMBER_ID")
    access_token = os.getenv("META_WHATSAPP_TOKEN")
    if not phone_number_id or not access_token:
        raise Exception("META_PHONE_NUMBER_ID ou META_WHATSAPP_TOKEN non configuré")
    to = phone if phone.startswith("+") else f"+222{phone}"
    data = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }).encode()
    req = urllib.request.Request(
        f"https://graph.facebook.com/v21.0/{phone_number_id}/messages",
        data=data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
        print(f"[Meta WhatsApp] to={to} — {result}")
        return result


def send_whatsapp_admin(message: str):
    phone = os.getenv("WHATSAPP_ADMIN_PHONE")
    apikey = os.getenv("WHATSAPP_CALLMEBOT_KEY")
    if not phone or not apikey:
        print("[WhatsApp] Variables WHATSAPP_ADMIN_PHONE ou WHATSAPP_CALLMEBOT_KEY manquantes")
        return
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={urllib.parse.quote(message)}&apikey={apikey}"
    try:
        urllib.request.urlopen(url, timeout=10)
        print(f"[WhatsApp] Notification envoyée : {message[:60]}")
    except Exception as e:
        print(f"[WhatsApp] Erreur envoi : {e}")

client = vonage.Client(
    key=os.getenv("VONAGE_API_KEY"),
    secret=os.getenv("VONAGE_API_SECRET")
)
sms = vonage.Sms(client)


def _send(phone: str, message: str):
    to = phone.lstrip("+") if phone.startswith("+") else f"222{phone}"
    response = sms.send_message({
        "from": "Goova",
        "to": to,
        "text": message,
    })
    msg = response["messages"][0]
    print(f"[Vonage] to={to} status={msg['status']} balance={msg.get('remaining-balance')} error={msg.get('error-text')}")
    if msg["status"] != "0":
        raise Exception(msg["error-text"])


def _send_whatsapp(phone: str, message: str):
    """Envoie un message WhatsApp via Green API."""
    instance_id = os.getenv("GREENAPI_INSTANCE_ID")
    token = os.getenv("GREENAPI_TOKEN")
    api_url = os.getenv("GREENAPI_URL", "https://api.green-api.com")
    if not instance_id or not token:
        raise Exception("GREENAPI_INSTANCE_ID ou GREENAPI_TOKEN non configuré")
    to = phone.lstrip("+") if phone.startswith("+") else f"222{phone}"
    chat_id = f"{to}@c.us"
    data = json.dumps({"chatId": chat_id, "message": message}).encode()
    req = urllib.request.Request(
        f"{api_url}/waInstance{instance_id}/sendMessage/{token}",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
        print(f"[Green API] to={chat_id} — {result}")
        return result


def send_whatsapp_otp(phone: str, otp: str):
    """Envoie un OTP via WhatsApp (UltraMsg). Fallback SMS Vonage si non configuré."""
    print(f"[WhatsApp OTP] phone={phone!r}")
    try:
        _send_whatsapp(phone, f"Goova - Votre code : {otp}. Valide 10 minutes.")
        return
    except Exception as e:
        print(f"[WhatsApp OTP] Erreur UltraMsg: {e} — fallback SMS")

    # Fallback Vonage SMS
    try:
        _send(phone, f"Goova - Votre code : {otp}. Valide 10 minutes.")
    except Exception as e:
        print(f"[OTP] SMS fallback non envoyé: {e}")


def send_otp_sms(phone: str, otp: str):
    try:
        _send(phone, f"Goova - Votre code : {otp}. Valide 10 minutes.")
    except Exception as e:
        print(f"OTP SMS non envoyé: {e}")


def send_booking_confirmation(phone: str, data: dict):
    message = (
        f"✅ *Goova — Réservation confirmée !*\n"
        f"Réf : {data['reference_code']}\n"
        f"Trajet : {data['from_city']} → {data['to_city']}\n"
        f"Date : {data['date']} à {data['time']}\n"
        f"Places : {data['seats']} | Total : {data['total_price']} MRU\n"
        f"Chauffeur : {data['driver_name']} — {data['driver_phone']}\n"
        f"Paiement en espèces au départ."
    )
    try:
        _send_whatsapp(phone, message)
    except Exception as e:
        print(f"[WhatsApp] Confirmation non envoyée: {e} — fallback SMS")
        try:
            _send(phone, message)
        except Exception as e2:
            print(f"[SMS] Confirmation non envoyée: {e2}")


def send_trip_reminder_passenger(phone: str, data: dict):
    message = (
        f"⏰ *Goova — Rappel trajet demain !*\n"
        f"{data['from_city']} → {data['to_city']}\n"
        f"Le {data['date']} à {data['time']}\n"
        f"Réf : {data['reference']}\n"
        f"Chauffeur : {data['driver_name']} — {data['driver_phone']}"
    )
    try:
        _send_whatsapp(phone, message)
    except Exception as e:
        print(f"[WhatsApp] Rappel passager non envoyé: {e} — fallback SMS")
        try:
            _send(phone, message)
        except Exception as e2:
            print(f"[SMS] Rappel passager non envoyé: {e2}")


def send_trip_reminder_driver(phone: str, data: dict):
    message = (
        f"⏰ *Goova — Rappel chauffeur demain !*\n"
        f"{data['from_city']} → {data['to_city']}\n"
        f"Le {data['date']} à {data['time']}\n"
        f"{data['passengers']} passager(s) vous attendent."
    )
    try:
        _send_whatsapp(phone, message)
    except Exception as e:
        print(f"[WhatsApp] Rappel chauffeur non envoyé: {e} — fallback SMS")
        try:
            _send(phone, message)
        except Exception as e2:
            print(f"[SMS] Rappel chauffeur non envoyé: {e2}")


def send_cancellation(phone: str, reference: str):
    message = f"❌ *Goova* — Réservation {reference} annulée. Contactez-nous si besoin."
    try:
        _send_whatsapp(phone, message)
    except Exception as e:
        print(f"[WhatsApp] Annulation non envoyée: {e} — fallback SMS")
        try:
            _send(phone, message)
        except Exception as e2:
            print(f"[SMS] Annulation non envoyée: {e2}")
