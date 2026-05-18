import os
import requests
from dotenv import load_dotenv

load_dotenv()

BUDGETSMS_USERNAME = os.getenv("BUDGETSMS_USERNAME")
BUDGETSMS_USERID = os.getenv("BUDGETSMS_USERID")
BUDGETSMS_HANDLE = os.getenv("BUDGETSMS_HANDLE")
API_URL = "https://api.budgetsms.net/sendsms/"


def _send(phone: str, message: str):
    to = f"222{phone}"
    params = {
        "username": BUDGETSMS_USERNAME,
        "handle": BUDGETSMS_HANDLE,
        "userid": BUDGETSMS_USERID,
        "to": to,
        "from": "Goova",
        "msg": message,
    }
    response = requests.get(API_URL, params=params)
    print(f"[BudgetSMS] to={to} status={response.status_code} response={response.text}")
    if response.status_code != 200 or "OK" not in response.text:
        raise Exception(response.text)


def send_otp_sms(phone: str, otp: str):
    try:
        _send(phone, f"Goova - Votre code : {otp}. Valide 10 minutes.")
    except Exception as e:
        print(f"OTP SMS non envoyé: {e}")


def send_booking_confirmation(phone: str, data: dict):
    message = (
        f"Goova Reservation confirmee !\n"
        f"Ref: {data['reference_code']}\n"
        f"Trajet: {data['from_city']} -> {data['to_city']}\n"
        f"Date: {data['date']} a {data['time']}\n"
        f"Places: {data['seats']} | Total: {data['total_price']} MRU\n"
        f"Chauffeur: {data['driver_name']} - {data['driver_phone']}\n"
        f"Paiement en especes au depart."
    )
    try:
        _send(phone, message)
    except Exception as e:
        print(f"SMS confirmation non envoyé: {e}")


def send_trip_reminder_passenger(phone: str, data: dict):
    message = (
        f"Goova Rappel trajet demain !\n"
        f"{data['from_city']} -> {data['to_city']}\n"
        f"Le {data['date']} a {data['time']}\n"
        f"Ref: {data['reference']}\n"
        f"Chauffeur: {data['driver_name']} - {data['driver_phone']}"
    )
    try:
        _send(phone, message)
    except Exception as e:
        print(f"SMS rappel passager non envoyé: {e}")


def send_trip_reminder_driver(phone: str, data: dict):
    message = (
        f"Goova Rappel chauffeur demain !\n"
        f"{data['from_city']} -> {data['to_city']}\n"
        f"Le {data['date']} a {data['time']}\n"
        f"{data['passengers']} passager(s) vous attendent."
    )
    try:
        _send(phone, message)
    except Exception as e:
        print(f"SMS rappel chauffeur non envoyé: {e}")


def send_cancellation(phone: str, reference: str):
    try:
        _send(phone, f"Goova - Reservation {reference} annulee. Contactez-nous au besoin.")
    except Exception as e:
        print(f"SMS annulation non envoyé: {e}")
