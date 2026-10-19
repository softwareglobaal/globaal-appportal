"""Eenmalig, 19-10-2026: de open mailpunten van klaarzet naar mailbericht, zodat er een bron is voor wat openstaat.

Driehoeksoverleg 19-10-2026 (3-0): de wachten, De Mailregisseur, het 08:00-bericht en /mail lezen dezelfde status. Tot
dan stonden de open punten als klaarzet-items voor mail-regisseur. Dit script zet ze over (app._mail_overgang), in een
transactie (BEGIN IMMEDIATE, zodat een wacht die tegelijk post moet wachten), met tellingen voor en na en een merker in
mailmeta. Het mag opnieuw draaien: wat al overgezet is, verandert niet. Ontwerptoets 19-10-2026: niet bij een webverzoek.

    docker compose exec -T app-mijnagents python eenmalig_mail_een_bron.py --droog   tonen, niets bewaren
    docker compose exec -T app-mijnagents python eenmalig_mail_een_bron.py           overzetten
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402


def tellingen(conn):
    return {
        "klaarzet klaar voor mail-regisseur": conn.execute(
            "SELECT COUNT(*) FROM klaarzet WHERE voor='mail-regisseur' AND status='klaar'").fetchone()[0],
        "open in mailbericht (_mail_open)": len(A._mail_open(conn)),
        "mailbericht met klaarzet_id": conn.execute("SELECT COUNT(*) FROM mailbericht WHERE klaarzet_id IS NOT NULL").fetchone()[0],
        "besluit van Mehdi": conn.execute("SELECT COUNT(*) FROM mailbericht WHERE besluit<>''").fetchone()[0],
    }


def overzetten(droog=False):
    """Geeft (voor, na, merker van een vorige keer). Faalt de controle, dan wordt niets bewaard."""
    with A.app.app_context():
        conn = A.db()
        A._mail_tabellen(conn)
        conn.execute("CREATE TABLE IF NOT EXISTS mailmeta (sleutel TEXT PRIMARY KEY, waarde TEXT)")
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        try:
            vorige = conn.execute("SELECT waarde FROM mailmeta WHERE sleutel='overgang_klaarzet'").fetchone()
            klaar = [r["id"] for r in conn.execute(
                "SELECT id FROM klaarzet WHERE voor='mail-regisseur' AND status='klaar'").fetchall()]
            voor = tellingen(conn)
            A._mail_overgang(conn)
            na = tellingen(conn)
            # Controle: elk item dat klaar stond, staat nu in mailbericht, open of met een besluit, en is opgepakt.
            zonder = [k for k in klaar if not conn.execute(
                "SELECT 1 FROM mailbericht WHERE klaarzet_id=? AND (opvolging IN ('open','onzeker') OR besluit<>'' "
                "OR opvolging IN ('beantwoord','doorgezet'))", (k,)).fetchone()]
            if zonder or na["klaarzet klaar voor mail-regisseur"]:
                raise SystemExit(f"controle mislukt, niets bewaard: zonder plaats in mailbericht {zonder[:20]}")
            if droog:
                conn.rollback()
            else:
                conn.execute("INSERT INTO mailmeta(sleutel, waarde) VALUES('overgang_klaarzet', ?) "
                             "ON CONFLICT(sleutel) DO UPDATE SET waarde=excluded.waarde",
                             (json.dumps({"ts": A.nu(), "voor": voor, "na": na}, ensure_ascii=False),))
                conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return voor, na, vorige[0] if vorige else None


if __name__ == "__main__":
    droog = "--droog" in sys.argv
    voor, na, vorige = overzetten(droog)
    if vorige:
        print(f"al eens gedaan: {vorige}")
    print("voor:", json.dumps(voor, ensure_ascii=False))
    print("na:  ", json.dumps(na, ensure_ascii=False))
    print("droog: niets bewaard" if droog else "bewaard")
