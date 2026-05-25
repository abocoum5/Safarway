from py_vapid import Vapid
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption
)
import base64

v = Vapid()
v.generate_keys()

private_pem = v.private_key.private_bytes(
    Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
).decode().strip()

public_b64 = base64.urlsafe_b64encode(
    v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
).rstrip(b"=").decode()

print("=" * 60)
print("Copie ces deux variables dans Render > Environment")
print("=" * 60)
print()
print("VAPID_PRIVATE_KEY =")
print(private_pem)
print()
print("VAPID_PUBLIC_KEY =")
print(public_b64)
print()
print("=" * 60)
