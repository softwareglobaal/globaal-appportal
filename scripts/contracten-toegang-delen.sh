#!/bin/bash
# Geeft siyan en angela toegang tot het contracten-dashboard (Authentik-groep).
# Gebruik:  bash ~/appportal/scripts/contracten-toegang-delen.sh
set -euo pipefail
cd "$HOME/appportal"
docker compose exec -T authentik-server ak shell -c 'exec(open("/dev/stdin").read())' <<'PY'
from authentik.core.models import Group, User
grp = Group.objects.get(name="contracten")
for naam in ("siyan", "angela"):
    u = User.objects.filter(username=naam).first()
    if u:
        u.groups.add(grp)
        print(f"TOEGEVOEGD: {naam} -> groep contracten")
    else:
        print(f"NIET GEVONDEN: {naam}")
print("KLAAR")
PY
