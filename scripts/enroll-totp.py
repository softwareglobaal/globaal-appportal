"""Enroll a CONFIRMED TOTP device with a known secret for the demo users, so an
automated end-to-end test can complete the (enforced) TOTP step. Test-only.
Run: sh scripts/ak-exec.sh scripts/enroll-totp.py
"""
from authentik.core.models import User

try:
    from authentik.stages.authenticator_totp.models import TOTPDevice
except ImportError:
    from django_otp.plugins.otp_totp.models import TOTPDevice

# Fixed 20-byte secret -> hex key (same bytes the test recomputes codes from).
SECRET = b"AppPortalTOTPsecret1"
KEY_HEX = SECRET.hex()

for uname in ("testmanager", "testadmin"):
    user = User.objects.get(username=uname)
    TOTPDevice.objects.filter(user=user).delete()
    TOTPDevice.objects.create(
        user=user, name="e2e", key=KEY_HEX, step=30, digits=6, confirmed=True
    )
    print(f"{uname}: confirmed TOTP device enrolled")
print(f"KEY_HEX={KEY_HEX}")
print("ENROLL_DONE")
