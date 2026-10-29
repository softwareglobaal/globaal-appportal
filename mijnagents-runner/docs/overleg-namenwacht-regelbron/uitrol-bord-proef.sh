T="$1"
run() { ( cd "$T/kloon" && HOME="$T/home" MIJNAGENTS_URL=http://127.0.0.1:3999 AGENTS_TOKEN=proeftoken bash "$T/cmd.sh" 2>&1 | grep -v -E '^(Traceback|  File|    )' ; exit "${PIPESTATUS[0]}" ); echo "exit $?"; }
sql() { python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(sys.argv[2]); c.commit()" "$T/kloon/mijnagents-data/mijnagents.db" "$1"; }
db() { python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print('  handelingen', c.execute('select count(*) from handeling').fetchone()[0], '| bord', [r[0] for r in c.execute('select substr(werkwijze,20,11) from agent order by naam')])" "$T/kloon/mijnagents-data/mijnagents.db"; }
LOG='Naamstructuur: 10 gelezen, 5 getoetst, 2 open punten; regelbron: bevestigde bron gelezen'
reset() { sql "delete from handeling"; for a in benamingen-wacht mappen-wacht; do python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute('update agent set werkwijze=? where naam=?', (open(sys.argv[2]).read().strip(), sys.argv[3])); c.commit()" "$T/kloon/mijnagents-data/mijnagents.db" "$T/$( [ $a = benamingen-wacht ] && echo bw11 || echo mw11).md" $a; done; echo "$LOG" > "$T/home/agents/benamingen_wacht.log"; echo "$LOG" > "$T/home/agents/mappen_wacht.log"; }
echo '=== A. normaal: bord 1.1'; reset; run; db
echo '=== B. herhaling: bord al 1.2'; run; db
echo '=== C. mappen-wacht tussentijds bewerkt'; reset; sql "update agent set werkwijze=werkwijze||' Extra zin.' where naam='mappen-wacht'"; run; db
echo '=== D. logboek zonder bevestigde regelbron'; reset; echo 'Naamstructuur: 1 gelezen; regelbron: regelboek gewijzigd; H-A-toetsing gepauzeerd' > "$T/home/agents/mappen_wacht.log"; run; db
echo '=== E. logboek ontbreekt'; reset; rm -f "$T/home/agents/mappen_wacht.log"; run; db
echo '=== F. herstel niet op de VM'; reset; git -C "$T/kloon" checkout -q --detach be8f4a0^; run; git -C "$T/kloon" checkout -q --detach 1edf580; db
echo '=== G. bord weigert (verkeerde groep)'; reset; sed -i '' 's/X-authentik-groups: admin/X-authentik-groups: niemand/' "$T/cmd.sh"; run; db
echo '=== H. Mehdi bewerkt tussen lezen en POST'; sed -i '' 's/X-authentik-groups: niemand/X-authentik-groups: admin/' "$T/cmd.sh"; reset; ( cd "$T/kloon" && PATH="$T/nepbin:$PATH" PROEF_DB="$T/kloon/mijnagents-data/mijnagents.db" HOME="$T/home" MIJNAGENTS_URL=http://127.0.0.1:3999 AGENTS_TOKEN=proeftoken bash "$T/cmd.sh" 2>&1 | grep -v -E '^(Traceback|  File|    )'; exit "${PIPESTATUS[0]}" ); echo "exit $?"; db
python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print('  versies mappen-wacht:', [r[0][-30:].replace(chr(10),' ') for r in c.execute(\"select tekst from werkwijze_versie where naam='mappen-wacht' order by id\")])" "$T/kloon/mijnagents-data/mijnagents.db"
