#!/bin/bash
# Nep-curl voor scenario H: Mehdi bewerkt de werkwijze van mappen-wacht via het bord vlak voor onze POST.
for x in "$@"; do case "$x" in *"/agent/mappen-wacht/werkwijze") /usr/bin/curl -s -o /dev/null -H 'X-authentik-username: mehdi' -H 'X-authentik-groups: admin' --data-urlencode "werkwijze=$(printf '%s\n\nTussentijdse zin van Mehdi.' "$(python3 -c "import sqlite3,os; print(sqlite3.connect(os.environ['PROEF_DB']).execute(\"select werkwijze from agent where naam='mappen-wacht'\").fetchone()[0])")")" http://127.0.0.1:3999/agent/mappen-wacht/werkwijze;; esac; done
exec /usr/bin/curl "$@"
