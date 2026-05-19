import os
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.auth import get_current_user

router = APIRouter(prefix="/push", tags=["Notifications Push"])

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_CLAIMS = {"sub": "mailto:contact@goova.mr"}


@router.get("/vapid-public-key")
def get_vapid_public_key():
    return {"public_key": VAPID_PUBLIC_KEY}


@router.post("/subscribe")
def subscribe(
    subscription: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    endpoint = subscription.get("endpoint")
    keys = subscription.get("keys", {})
    p256dh = keys.get("p256dh", "")
    auth = keys.get("auth", "")

    if not endpoint or not p256dh or not auth:
        raise HTTPException(status_code=400, detail="Données d'abonnement invalides")

    existing = db.query(models.PushSubscription).filter(
        models.PushSubscription.endpoint == endpoint
    ).first()

    if existing:
        existing.user_id = current_user.id
        existing.p256dh = p256dh
        existing.auth = auth
    else:
        db.add(models.PushSubscription(
            user_id=current_user.id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
        ))

    db.commit()
    return {"message": "Abonnement enregistré"}


@router.delete("/subscribe")
def unsubscribe(endpoint: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db.query(models.PushSubscription).filter(
        models.PushSubscription.endpoint == endpoint,
        models.PushSubscription.user_id == current_user.id
    ).delete()
    db.commit()
    return {"message": "Désabonnement effectué"}


def send_push_to_user(db: Session, user_id: int, payload: dict):
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        return

    subscriptions = db.query(models.PushSubscription).filter(
        models.PushSubscription.user_id == user_id
    ).all()

    if not subscriptions:
        return

    try:
        from pywebpush import webpush, WebPushException
        data = json.dumps(payload)
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=data,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=dict(VAPID_CLAIMS),
                )
            except WebPushException as e:
                print(f"[Push] Erreur: {e}")
                if "410" in str(e) or "404" in str(e):
                    db.delete(sub)
                    db.commit()
    except ImportError:
        print("[Push] pywebpush non installé")
