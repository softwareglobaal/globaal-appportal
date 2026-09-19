"""Grendel: de Agendawacht mag uit het archief lezen maar er nooit in schrijven.

Mandaat van Mehdi, 20-09-2026. De agent draait op zijn eigen Google-account en
heeft daar overal schrijfrecht, dus Google houdt hem niet tegen. Deze test doet
dat wel: hij faalt zodra iemand de grendel weghaalt of een archiefagenda in
KALENDERS zet.
"""
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


# harchitectsbvba is sinds 20-09-2026 "Prive agenda mehdi", zijn privé-agenda,
# en dus geen archief meer. De oude groepsagenda Prive Buiten wel.
ACTIEF = ["mehdiprivewerkagenda@gmail.com",
          "73e8b6359d04b7bdb02aa045e668cd6f9d9f007bec51ce370494e7de7501f0c4@group.calendar.google.com",
          "harchitectsbvba@gmail.com"]
ARCHIEF = ["haagendalightprojects@gmail.com",
           "bfe28ee64dc72b449582af5e6a9fc6af3669709adf07adc8b49eb97666f07981@group.calendar.google.com",
           "projects@h-architects.be", "privehragendamehdi@gmail.com",
           "unabosdp@gmail.com", "hdslelydorp@gmail.com", "mch.remindersagenda@gmail.com",
           "mehdienfamilie@gmail.com", "operationsenmehdi@gmail.com", "outofofficesr@gmail.com",
           "hr.harchitects22@gmail.com", "melodiebvba@gmail.com"]

# De namen niet ophalen bij Google: de test moet ook zonder netwerk draaien.
W.gearchiveerd = lambda: set()

for kal in ACTIEF:
    check(f"schrijven mag in {kal[:34]}", W.mag_schrijven(kal))
for kal in ARCHIEF:
    check(f"schrijven geweigerd in {kal[:30]}", not W.mag_schrijven(kal))

check("een agenda op ZZ ARCHIEF wordt geweigerd ook al staat hij in KALENDERS",
      (lambda: (setattr(W, "gearchiveerd", lambda: {ACTIEF[0]}),
                not W.mag_schrijven(ACTIEF[0]))[1])())

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
