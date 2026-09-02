#!/bin/bash
# Maakt de Authentik-groep 'contracten-bewerken' (schrijfrecht voor de
# MCP-koppeling van het contractsysteem) en zet mehdi erin.
# Gebruik:  bash ~/appportal/scripts/contracten-bewerken-groep.sh [extra gebruikersnaam ...]
set -euo pipefail
cd "$HOME/appportal"
LEDEN="mehdi $*"
docker compose exec -T -e LEDEN="$LEDEN" authentik-server ak shell -c 'exec(open("/dev/stdin").read())' <<'PY'
import os
from authentik.core.models import Group, User
grp, nieuw = Group.objects.get_or_create(name="contracten-bewerken")
print("GROEP:", grp.name, "(nieuw aangemaakt)" if nieuw else "(bestond al)")
for naam in os.environ.get("LEDEN", "").split():
    u = User.objects.filter(username=naam).first()
    if u:
        u.groups.add(grp)
        print(f"TOEGEVOEGD: {naam} -> {grp.name}")
    else:
        print(f"NIET GEVONDEN: {naam}")
print("KLAAR — verbind daarna de connector opnieuw in claude.ai (het token onthoudt het schrijfrecht bij het inloggen).")
PY
