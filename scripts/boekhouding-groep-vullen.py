"""Zet de gebruikers uit BOEKHOUDING_USERS in de Authentik-groep `boekhouding`.

Draaien (vanuit ~/appportal):
  BOEKHOUDING_USERS=joan sh scripts/ak-exec.sh scripts/boekhouding-groep-vullen.py

Zonder BOEKHOUDING_USERS toont het script alleen wie er nu in de groep zit en
welke gebruikers er zoal bestaan met een naam die op de opgegeven zoekterm
lijkt (BOEKHOUDING_ZOEK). Idempotent.
"""
import os

from authentik.core.models import Group, User

groep, gemaakt = Group.objects.get_or_create(name="boekhouding")
print(f"groep boekhouding: {'aangemaakt' if gemaakt else 'bestond al'}")
print("leden nu:", ", ".join(u.username for u in groep.users.all()) or "geen")

zoek = os.environ.get("BOEKHOUDING_ZOEK", "").strip()
if zoek:
    treffers = User.objects.filter(username__icontains=zoek) | User.objects.filter(
        name__icontains=zoek)
    print(f"gebruikers die lijken op {zoek!r}:",
          ", ".join(f"{u.username} ({u.name})" for u in treffers.distinct()) or "geen")

namen = [n.strip() for n in os.environ.get("BOEKHOUDING_USERS", "").split(",") if n.strip()]
for naam in namen:
    gebruiker = User.objects.filter(username=naam).first()
    if not gebruiker:
        print(f"NIET GEVONDEN: {naam}")
        continue
    groep.users.add(gebruiker)
    print(f"toegevoegd: {gebruiker.username} ({gebruiker.name})")
groep.save()
print("leden na afloop:", ", ".join(u.username for u in groep.users.all()) or "geen")
print("BOEKHOUDING_GROEP_DONE")
