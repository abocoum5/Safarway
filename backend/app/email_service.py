import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(to_email: str, otp: str):
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = "SafarWay — Code de connexion Admin"

    body = f"""
    Bonjour,

    Votre code de connexion SafarWay Admin est :

    ━━━━━━━━━━━━━━━━━
         {otp}
    ━━━━━━━━━━━━━━━━━

    Ce code expire dans 10 minutes.
    Si vous n'avez pas demandé ce code, ignorez cet email.

    SafarWay
    """
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)