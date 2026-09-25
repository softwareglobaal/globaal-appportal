"""Logins per e-mailadres uit Bitwarden naar communicatie.emailadres_dienst (migratie 173).

Draait op de pc waar `bw serve` luistert (standaard localhost:8087), met een
ontgrendelde en gesynchroniseerde kluis. Schrijft SQL naar stdout; die SQL
pijp je naar de database op de VM:

    python scripts/bitwarden-diensten-laden.py --domein qoppa.be > laden.sql
    cat laden.sql | plink -batch ubuntu@54.80.98.233 "docker exec -i appportal-postgresql-1 sh -c 'psql -U \\$POSTGRES_USER -d appportal -f -'"

Wat er NOOIT uitgaat: wachtwoorden, TOTP, notities, velden, kaarten,
identiteiten, bijlagen en wachtwoordgeschiedenis. Per item blijft alleen over:
het Bitwarden-id, de naam, de collectie, de host van de login-URL en de
gebruikersnaam als die een e-mailadres is. Een gebruikersnaam die geen
e-mailadres is, wordt niet meegenomen.

Idempotent: bestaande rijen worden bijgewerkt, en rijen van adressen binnen de
scope die niet meer in de kluis staan, worden verwijderd. Logins op een adres
dat niet in het register staat, worden niet stil overgeslagen: de SQL meldt
hoeveel het er zijn en welke adressen.
"""
import argparse
import json
import re
import sys
import urllib.request
from urllib.parse import urlparse

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def haal(basis, pad):
    with urllib.request.urlopen(basis + pad, timeout=120) as r:
        d = json.load(r)
    if not d.get("success"):
        raise SystemExit(f"bw serve gaf geen succes op {pad}")
    return d["data"]["data"]


def host(uri):
    try:
        u = urlparse(uri if "://" in uri else "https://" + uri)
        return (u.hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""


def is_mailbox_host(h):
    return "one.com" in h or h.startswith("mail.") or h.startswith("webmail.")


def q(s):
    return "'" + str(s).replace("'", "''") + "'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domein", help="alleen adressen op dit domein, bv. qoppa.be")
    ap.add_argument("--basis", default="http://localhost:8087")
    a = ap.parse_args()

    status = json.load(urllib.request.urlopen(a.basis + "/status", timeout=10))["data"]["template"]
    if status.get("status") != "unlocked":
        raise SystemExit("De kluis is niet ontgrendeld.")
    collecties = {c["id"]: c["name"] for c in haal(a.basis, "/list/object/collections")}

    rijen = []
    for it in haal(a.basis, "/list/object/items"):
        login = it.get("login") or {}
        gebruiker = (login.get("username") or "").strip().lower()
        if not EMAIL.match(gebruiker):
            continue
        if a.domein and not gebruiker.endswith("@" + a.domein.lower()):
            continue
        hosts = sorted({h for h in (host(u.get("uri") or "") for u in (login.get("uris") or [])) if h})
        buiten = [h for h in hosts if not is_mailbox_host(h)]
        soort = "dienst" if buiten else ("mailbox" if hosts else "onbekend")
        coll = ", ".join(sorted(collecties.get(c, "?") for c in (it.get("collectionIds") or [])))
        rijen.append((gebruiker, it["id"], soort, buiten[0] if buiten else "", it.get("name") or "", coll))

    peil = status.get("lastSync") or ""
    print("-- Bitwarden-logins naar communicatie.emailadres_dienst")
    print(f"-- scope: {a.domein or 'alle domeinen'}, items: {len(rijen)}, kluis gesynchroniseerd: {peil}")
    print("BEGIN;")
    print("CREATE TEMP TABLE bw_in (adres text, bitwarden_id text, soort text, dienst text, naam text, collectie text) ON COMMIT DROP;")
    if rijen:
        print("INSERT INTO bw_in VALUES")
        print(",\n".join("  (" + ", ".join(q(x) for x in r) + ")" for r in rijen) + ";")
    print(f"""
-- Niet stil overslaan: logins op adressen die niet in het register staan.
DO $$
DECLARE n int; lijst text;
BEGIN
  SELECT count(*), string_agg(DISTINCT b.adres, ', ') INTO n, lijst
    FROM bw_in b LEFT JOIN communicatie.emailadres e ON lower(e.adres::text) = b.adres
   WHERE e.id IS NULL;
  RAISE NOTICE 'logins op adressen buiten het register: % (%)', n, coalesce(lijst, '-');
END $$;

INSERT INTO communicatie.emailadres_dienst
       (emailadres_id, bitwarden_id, soort, dienst, naam, collectie, bron, bron_bijgewerkt_op)
SELECT e.id, b.bitwarden_id, b.soort, b.dienst, b.naam, b.collectie, 'bitwarden', {q(peil)}::timestamptz
  FROM bw_in b JOIN communicatie.emailadres e ON lower(e.adres::text) = b.adres
ON CONFLICT (emailadres_id, bitwarden_id) DO UPDATE
   SET soort = EXCLUDED.soort, dienst = EXCLUDED.dienst, naam = EXCLUDED.naam,
       collectie = EXCLUDED.collectie, bron_bijgewerkt_op = EXCLUDED.bron_bijgewerkt_op;

-- Wat binnen de scope niet meer in de kluis staat, gaat eruit.
DELETE FROM communicatie.emailadres_dienst d
 USING communicatie.emailadres e
 WHERE e.id = d.emailadres_id
   AND {("lower(e.adres::text) LIKE " + q('%@' + a.domein.lower())) if a.domein else "true"}
   AND d.bitwarden_id NOT IN (SELECT bitwarden_id FROM bw_in);

SELECT soort, count(*) AS logins, count(DISTINCT emailadres_id) AS adressen
  FROM communicatie.emailadres_dienst d JOIN communicatie.emailadres e ON e.id = d.emailadres_id
 WHERE {("lower(e.adres::text) LIKE " + q('%@' + a.domein.lower())) if a.domein else "true"}
 GROUP BY soort ORDER BY soort;
COMMIT;""")


if __name__ == "__main__":
    main()
