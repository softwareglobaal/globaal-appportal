"""TEST-ONLY: allow password-only login (no TOTP) so the portal can be inspected.

Sets the MFA validation stage to skip when no authenticator is configured, and
removes the demo users' TOTP devices (a user WITH a device is still prompted,
regardless of the skip setting).

Re-enable later with:  sh scripts/configure-authentik.sh   (restores enforcement)
                       sh scripts/ak-exec.sh scripts/enroll-totp.py   (re-adds demo device)

Run: sh scripts/ak-exec.sh scripts/disable-totp.py
"""
from authentik.core.models import User
from authentik.stages.authenticator_validate.models import AuthenticatorValidateStage

try:
    from authentik.stages.authenticator_validate.models import NotConfiguredAction

    SKIP = NotConfiguredAction.SKIP
except Exception:
    SKIP = "skip"

try:
    from authentik.stages.authenticator_totp.models import TOTPDevice
except ImportError:
    from django_otp.plugins.otp_totp.models import TOTPDevice

mfa = AuthenticatorValidateStage.objects.filter(
    name="default-authentication-mfa-validation"
).first()
if mfa:
    mfa.not_configured_action = SKIP
    mfa.save()
    print(f"mfa stage: not_configured_action = {SKIP} (password-only login allowed)")
else:
    print("WARNING: default-authentication-mfa-validation stage not found")

removed = 0
for uname in ("testmanager", "testadmin"):
    user = User.objects.filter(username=uname).first()
    if user:
        removed += TOTPDevice.objects.filter(user=user).delete()[0]
print(f"removed {removed} TOTP device(s) from demo users")
print("TOTP_DISABLED")
