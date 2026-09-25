#!/usr/bin/env python3
"""Sorteert de INBOX van een one.com-mailbox volgens een regelbestand. Alleen verplaatsen.

Bron: repo softwareglobaal/globaal-appportal, mijnagents-runner/mailregels/ (sinds 26-9-2026). Op de Mac wijst
~/.claude/tools/mailopruiming/sorteren.py hierheen; de mailwachten op de VM gebruiken dezelfde regels.

Gebruik: sorteren.py <alias> <regels.txt> [--sinds Nd|ALL] [--doe] [--rapport MAP] [--nieuwe-reclame]

  --sinds 3d        alleen berichten van de laatste 3 dagen (standaard ALL)
  --doe             echt verplaatsen; zonder --doe alleen tellen en rapporteren
  --rapport MAP     schrijf rapport (json + md) en een logregel in die map
  --nieuwe-reclame  onbekende afzender met List-Unsubscribe-kop en zonder transactie in het
                    onderwerp gaat naar INBOX.Opgeruimd; apart gemeld zodat je hem kunt terugzetten

Vier harde regels, bewaakt in test_sorteren.py:
1. Er wordt nooit iets verwijderd: geen \\Deleted, geen EXPUNGE, alleen UID MOVE.
2. Lezen verandert niets: BODY.PEEK en readonly zolang er niet met --doe verplaatst wordt.
3. Niets gebeurt stil: elk verplaatst bericht staat in het rapport met afzender en onderwerp.
4. Regels staan in het regelbestand, niet in de code; de code kent geen afzenders.
26-9-2026: mapnamen gaan altijd tussen aanhalingstekens naar de server (imapnaam).
"""
import collections
import datetime as dt
import email
import json
import os
import re
import sys
import unicodedata
from email.utils import parseaddr, parsedate_to_datetime

from email.header import decode_header, make_header

# onemail.py (de Keychain van de Mac) is alleen nodig om als commando een mailbox te openen. De mailwachten op de VM
# gebruiken alleen de regels (laad_regels, bestemming, imapnaam) en openen de mailbox via de postbus.
onemail = None


def _onemail(alias):
    global onemail
    if onemail is None:
        sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
        _argv = sys.argv
        sys.argv = ["onemail", alias, "check"]
        import onemail as _om  # noqa: E402
        sys.argv = _argv
        onemail = _om
    return onemail


def dec(v):
    try:
        return str(make_header(decode_header(v or "")))
    except Exception:  # noqa: BLE001
        return v or ""

OPGERUIMD = "INBOX.Opgeruimd"
TRANSACTIE = re.compile(r"order|bestel|factu|invoice|payment|betaal|betaling|verzond|verzend|shipment|"
                        r"on the way|onderweg|delivered|geleverd|bezorgd|confirmed|bevestig|account|renewal|"
                        r"wachtwoord|password|ticket|offerte|quote|re:|fw:", re.I)


def _plat(s):
    return unicodedata.normalize("NFKC", s or "").lower()


def laad_regels(pad):
    exact, domein, suffix, oplichting, eigen = {}, {}, [], [], []
    archief = {"dagen": None, "map": None}
    sectie = None
    for regel in open(pad, encoding="utf-8"):
        regel = regel.strip()
        if not regel or regel.startswith("#"):
            continue
        if regel.startswith("[") and regel.endswith("]"):
            sectie = regel[1:-1]
            continue
        if sectie == "oplichting":
            naam, _, domeinen = regel.partition("=")
            if naam.strip().lower() == "eigen":
                eigen.extend(d.strip().lower() for d in domeinen.split(",") if d.strip())
                continue
            oplichting.append((_plat(naam.strip()), [d.strip().lower() for d in domeinen.split(",") if d.strip()]))
        elif sectie == "archief":
            k, _, v = regel.partition("=")
            archief[k.strip()] = v.strip()
        elif sectie:
            r = regel.lower()
            if r.startswith("."):
                suffix.append((r, sectie))
            elif r.startswith("@"):
                domein[r] = sectie
            else:
                exact[r] = sectie
    archief["dagen"] = int(archief["dagen"]) if archief.get("dagen") else None
    return {"exact": exact, "domein": domein, "suffix": suffix, "oplichting": oplichting, "eigen": eigen, "archief": archief}


def is_oplichting(naam, adres, regels):
    """True als de afzendernaam een merk claimt dat niet bij het domein hoort."""
    naam_p, adres_p = _plat(naam), _plat(adres)
    dom = adres_p.split("@")[-1]
    if any(dom == d or dom.endswith("." + d) for d in regels["eigen"]):
        return False  # eigen domeinen zijn nooit oplichting
    for merk, echt in regels["oplichting"]:
        # aan het begin van een woord; korte merken (ING, CM, KBO) ook aan het einde, anders raakt "ING" Kingsberry
        pat = r"(?<![a-z0-9])" + re.escape(merk) + (r"(?![a-z0-9])" if len(merk) <= 3 else "")
        if re.search(pat, naam_p):
            if not any(dom == d or dom.endswith("." + d) for d in echt):
                return True
    return False


def bestemming(rij, regels, nieuwe_reclame, archief_grens):
    """Geeft (map of None, reden)."""
    adres, naam = rij["addr"], rij["name"]
    if not adres or "@" not in adres:
        return OPGERUIMD, "geen afzender"
    if is_oplichting(naam, adres, regels):
        return OPGERUIMD, "oplichting"
    if adres in regels["exact"]:
        return regels["exact"][adres], "adres"
    dom = "@" + adres.split("@")[-1]
    if dom in regels["domein"]:
        return regels["domein"][dom], "domein"
    for suf, m in regels["suffix"]:
        if adres.endswith(suf) or adres.endswith("@" + suf[1:]):
            return m, "domein"
    if nieuwe_reclame and rij["unsub"] and not TRANSACTIE.search(rij["subject"] or ""):
        return OPGERUIMD, "nieuwe reclame"
    if archief_grens and rij["datum"] and rij["datum"] < archief_grens:
        return regels["archief"]["map"].replace("{jaar}", str(rij["datum"].year)), "archief"
    return None, "blijft"


def haal_koppen(m, sinds):
    st, d = m.uid("search", None, f"SINCE {sinds}" if sinds else "ALL")
    uids = d[0].split()
    rijen = []
    for i in range(0, len(uids), 200):
        chunk = b",".join(uids[i:i + 200])
        st, data = m.uid("fetch", chunk, "(INTERNALDATE BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE LIST-UNSUBSCRIBE)])")
        for item in data:
            if not isinstance(item, tuple):
                continue
            meta = item[0].decode("utf-8", "replace")
            uid = int(re.search(r"UID (\d+)", meta).group(1))
            hdr = email.message_from_bytes(item[1])
            naam, adres = parseaddr(dec(hdr.get("From")))
            datum = None
            try:
                datum = parsedate_to_datetime(hdr.get("Date"))
                if datum.tzinfo is None:
                    datum = datum.replace(tzinfo=dt.timezone.utc)
            except Exception:
                mi = re.search(r'INTERNALDATE "([^"]+)"', meta)
                if mi:
                    try:
                        datum = dt.datetime.strptime(mi.group(1), "%d-%b-%Y %H:%M:%S %z")
                    except ValueError:
                        datum = None
            rijen.append(dict(uid=uid, name=naam, addr=adres.lower(), subject=dec(hdr.get("Subject"))[:120],
                              datum=datum, unsub=bool(hdr.get("List-Unsubscribe"))))
    return rijen


def imapnaam(naam):
    """Een mapnaam tussen aanhalingstekens voor de server. Zonder aanhalingstekens leest one.com
    'INBOX.Bank en verzekering' als 'INBOX.Bank' (gezien 26-9-2026: de map INBOX.Accounts ontstond zo)."""
    return '"' + naam.replace("\\", "\\\\").replace('"', '\\"') + '"'


def bestaande_mappen(m):
    st, lijst = m.list()
    uit = set()
    for l in lijst or []:
        s = l.decode("utf-8", "replace").rstrip()
        mm = re.search(r'"([^"]+)"$', s)
        uit.add(mm.group(1) if mm else s.split(" ")[-1])
    return uit


def maak_map(m, naam, bestaande):
    if naam in bestaande:
        return
    st, _ = m.create(imapnaam(naam))
    assert st == "OK", f"map {naam} aanmaken mislukt"
    m.subscribe(imapnaam(naam))
    bestaande.add(naam)


def schrijf_rapport(rapportmap, stempel, sinds, DOE, rijen, per_map, blijft, user="info@h-invest.be"):
    os.makedirs(rapportmap, exist_ok=True)
    dag = dt.date.today().isoformat()

    def rij_txt(r):
        d = r["datum"].strftime("%d-%m-%Y") if r["datum"] else "?"
        return f"- {d} | {r['name'] or ''} <{r['addr']}> | {r['subject']}"

    verplaatst = sum(len(v) for v in per_map.values())
    md = [f"# Mailwacht {user}, {stempel}", "",
          f"Bekeken: {len(rijen)} berichten ({'sinds ' + sinds if sinds else 'alles'}). "
          f"{'Verplaatst' if DOE else 'Zou verplaatsen (droog)'}: {verplaatst}. Blijft in INBOX: {len(blijft)}.", ""]
    opl = [r for rs in per_map.values() for r in rs if r["reden"] == "oplichting"]
    nieuw = [r for rs in per_map.values() for r in rs if r["reden"] == "nieuwe reclame"]
    if opl:
        md += ["## Oplichting (naar Opgeruimd, nooit op klikken)"] + [rij_txt(r) for r in opl] + [""]
    if nieuw:
        md += ["## Nieuwe reclame (automatisch naar Opgeruimd; hoort er een niet, zet hem terug en voeg een regel toe)"] + [rij_txt(r) for r in nieuw] + [""]
    md += ["## Blijft in INBOX (dit zien de mensen van deze mailbox)"] + [rij_txt(r) for r in blijft[:200]] + [""]
    md += ["## Per map"]
    for doel, rs in sorted(per_map.items(), key=lambda x: -len(x[1])):
        md.append(f"### {doel} ({len(rs)})")
        md += [rij_txt(r) for r in rs[:60]]
        if len(rs) > 60:
            md.append(f"- ... en nog {len(rs) - 60}")
        md.append("")
    tekst = "\n".join(md)
    open(os.path.join(rapportmap, f"mailwacht {dag}.md"), "w", encoding="utf-8").write(tekst)
    open(os.path.join(rapportmap, "laatste.md"), "w", encoding="utf-8").write(tekst)
    with open(os.path.join(rapportmap, "logboek.md"), "a", encoding="utf-8") as f:
        f.write(f"{stempel} | bekeken {len(rijen)} | verplaatst {verplaatst if DOE else 0} | blijft {len(blijft)}"
                f" | oplichting {len(opl)} | nieuwe reclame {len(nieuw)} | {'echt' if DOE else 'droog'}\n")
    json.dump({"tijd": stempel, "doe": DOE,
               "per_map": {k: [dict(r, datum=str(r["datum"])) for r in v] for k, v in per_map.items()},
               "blijft": [dict(r, datum=str(r["datum"])) for r in blijft]},
              open(os.path.join(rapportmap, "laatste.json"), "w"), ensure_ascii=False, indent=0, default=str)


def main():
    a = sys.argv[1:]
    alias, regelpad = a[0], a[1]
    DOE, NIEUW = "--doe" in a, "--nieuwe-reclame" in a
    sinds = None
    if "--sinds" in a:
        w = a[a.index("--sinds") + 1]
        if w.upper() != "ALL":
            sinds = (dt.date.today() - dt.timedelta(days=int(w.rstrip("d")))).strftime("%d-%b-%Y")
    rapportmap = a[a.index("--rapport") + 1] if "--rapport" in a else None
    regels = laad_regels(regelpad)
    grens = None
    if regels["archief"]["dagen"]:
        grens = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=regels["archief"]["dagen"])

    om = _onemail(alias)
    user = om.ALIASES.get(alias, alias)
    m = om.connect(user, "INBOX", readonly=not DOE)
    rijen = haal_koppen(m, sinds)
    per_map, blijft = collections.defaultdict(list), []
    for r in rijen:
        doel, reden = bestemming(r, regels, NIEUW, grens)
        r["reden"] = reden
        (per_map[doel] if doel else blijft).append(r)

    stempel = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"{user} INBOX: {len(rijen)} berichten bekeken ({'sinds ' + sinds if sinds else 'alles'})", "(droog)" if not DOE else "")
    if DOE and per_map:
        assert om.kan_move(m), "server kent UID MOVE niet; niets gedaan"
        bestaand = bestaande_mappen(m)
        for doel in per_map:
            maak_map(m, doel, bestaand)
    for doel, rs in sorted(per_map.items(), key=lambda x: -len(x[1])):
        redenen = collections.Counter(r["reden"] for r in rs)
        print(f"  {len(rs):5} -> {doel}  ({', '.join(f'{k} {v}' for k, v in redenen.items())})")
        if DOE:
            uids = [str(r["uid"]) for r in rs]
            for i in range(0, len(uids), 100):
                st, d = m.uid("MOVE", ",".join(uids[i:i + 100]), imapnaam(doel))
                assert st == "OK", (doel, d)
    print(f"  {len(blijft):5} blijft in INBOX")
    m.logout()
    if rapportmap:
        schrijf_rapport(rapportmap, stempel, sinds, DOE, rijen, per_map, blijft, user)


if __name__ == "__main__":
    main()
