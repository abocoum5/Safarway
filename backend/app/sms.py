import os
import requests
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
API_URL = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"


def _send_whatsapp(phone: str, template: str, lang: str = "en_US", components: list = None):
    to = f"222{phone}"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": lang},
        }
    }
    if components:
        payload["template"]["components"] = components

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.post(API_URL, json=payload, headers=headers)
    data = response.json()
    print(f"[WhatsApp] to={to} status={response.status_code} response={data}")
    if response.status_code != 200:
        raise Exception(data)
    return data


def send_otp_sms(phone: str, otp: str):
    try:
        components = [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": otp}]
            }
        ]
        _send_whatsapp(phone, "otp_verification", lang="fr", components=components)
    except Exception as e:
        print(f"OTP WhatsApp non envoyé: {e}")


def send_booking_confirmation(phone: str, data: dict):
    try:
        _send_whatsapp(phone, "hello_world")
    except Exception as e:
        print(f"WhatsApp confirmation non envoyé: {e}")


def send_trip_reminder_passenger(phone: str, data: dict):
    try:
        _send_whatsapp(phone, "hello_world")
    except Exception as e:
        print(f"WhatsApp rappel passager non envoyé: {e}")


def send_trip_reminder_driver(phone: str, data: dict):
    try:
        _send_whatsapp(phone, "hello_world")
    except Exception as e:
        print(f"WhatsApp rappel chauffeur non envoyé: {e}")


def send_cancellation(phone: str, reference: str):
    try:
        _send_whatsapp(phone, "hello_world")
    except Exception as e:
        print(f"WhatsApp annulation non envoyé: {e}")
