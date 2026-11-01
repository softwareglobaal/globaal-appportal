#!/usr/bin/env python3
"""Het adres van de zetel van beide firma's in kern, uit de KBO (01-11-2026).

De scheiding (scheiding.laad_kern) eist van beide firma's een ondernemingsnummer en een adres in kern; zonder werkt Bouw
niet. Op 01-11-2026 had kern voor geen enkele firma een adres. Dit vult het, alleen waar het leeg is, uit de openbare
KBO-pagina van het ondernemingsnummer dat al in kern staat. Een adres dat er al staat, blijft ongemoeid. Het drukt nooit
een adres af: alleen wat het deed.

Op de VM, in mijnagents-runner (zonder --schrijf zegt het alleen wat het zou doen):
    ~/agents/.venv/bin/python -m bouw.kern_adres [--schrijf]
"""
import html
import re
import sys
import urllib.request

from . import scheiding as S

KBO_URL = "https://kbopub.economie.fgov.be/kbopub/toonondernemingps.html?ondernemingsnummer={}&lang=nl"
DOOR = "bouw-kern-adres (KBO)"
SQL_LEES = ("select json_agg(json_build_object('code', f.code, 'kbo', coalesce(f.kbo_nummer, ''), 'adres_id', f.adres_id, "
            "'straat', coalesce(a.straat, ''), 'nr', coalesce(a.huisnummer, ''))) "
            "from kern.firma f left join kern.adres a on a.id = f.adres_id where f.code in ('HARC', 'HARM')")
STRAAT = re.compile(r"^(?P<straat>\D.*?)\s+(?P<nr>\d+[A-Za-z]?(?:\s*-\s*\d+[A-Za-z]?)?(?:\s+bus\s+\S+)?)$", re.I)
POSTCODE = re.compile(r"^(?P<postcode>[1-9]\d{3})\s+(?P<gemeente>\S.*)$")


def q(waarde):
    return "'" + str(waarde).replace("'", "''") + "'"


def _cel(pagina, label):
    m = re.search(rf"(?is){label}\s*:?\s*</td>\s*<td[^>]*>(.*?)</td>", pagina or "")
    return m.group(1) if m else ""


def _regels(cel):
    cel = re.sub(r"(?is)<span[^>]*class=\"upd\"[^>]*>.*?</span>", "", cel)    # "Sinds 22 mei 2023"
    t = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?i)<br\s*/?>", "\n", cel))).replace("\xa0", " ")
    return [" ".join(r.split()) for r in t.splitlines() if r.strip()]


def zetel(pagina, nummer):
    """{straat, huisnummer, postcode, gemeente} van de zetel op de KBO-pagina van precies dit nummer, of None als de
    pagina een ander nummer toont of het adres niet in de vaste vorm staat (straat met nummer, dan postcode en gemeente)."""
    kaal = re.sub(r"\D", "", nummer or "").zfill(10)
    if len(kaal) != 10 or re.sub(r"\D", "", " ".join(_regels(_cel(pagina, "Ondernemingsnummer")))) != kaal:
        return None
    regels = _regels(_cel(pagina, "Adres van de zetel"))
    if len(regels) != 2:
        return None
    s, p = STRAAT.match(regels[0]), POSTCODE.match(regels[1])
    if not s or not p:
        return None
    return {"straat": s["straat"], "huisnummer": s["nr"], "postcode": p["postcode"], "gemeente": p["gemeente"]}


def haal(url):
    verzoek = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (mijnagents bouw)"})
    with urllib.request.urlopen(verzoek, timeout=30) as antwoord:
        return antwoord.read().decode(antwoord.headers.get_content_charset() or "utf-8", errors="replace")


def vul(psql, haal=haal, schrijf=False):
    """Een regel per firma met wat er gebeurde; zet alleen een adres waar kern.firma nog geen adres heeft."""
    rijen = {r.get("code"): r for r in (psql(SQL_LEES) or [])}
    uit = []
    for code in S.KERN_CODES:
        r = rijen.get(code)
        if not r:
            uit.append(f"{code}: niet in kern.firma")
            continue
        if r.get("adres_id"):
            uit.append(f"{code}: heeft al een adres in kern, ongemoeid"
                       + ("" if r.get("straat") and r.get("nr") else " (zonder straat of nummer: met de hand nakijken)"))
            continue
        kaal = re.sub(r"\D", "", r.get("kbo") or "").zfill(10)
        if len(kaal) != 10:
            uit.append(f"{code}: geen ondernemingsnummer in kern")
            continue
        try:
            z = zetel(haal(KBO_URL.format(kaal)), kaal)
        except OSError as e:
            uit.append(f"{code}: KBO niet gelezen ({type(e).__name__})")
            continue
        if not z:
            uit.append(f"{code}: zetel niet gelezen op de KBO-pagina")
            continue
        if not schrijf:
            uit.append(f"{code}: zou het adres van de zetel uit de KBO zetten")
            continue
        weergave = f"{z['straat']} {z['huisnummer']}, {z['postcode']} {z['gemeente']}"
        aid = (psql(f"select json_build_object('id', kern.adres_vind_of_maak({q(weergave)}, {q(DOOR)}))") or {}).get("id")
        if not aid:
            uit.append(f"{code}: adres niet gemaakt in kern")
            continue
        # Twee stappen: een update in dezelfde opdracht als adres_vind_of_maak ziet de nieuwe rij niet. Een gedeelde rij
        # wordt alleen aangevuld als al haar velden leeg zijn (Codex, controle 11)
        res = psql(f"with u as (update kern.adres set straat = {q(z['straat'])}, huisnummer = {q(z['huisnummer'])}, "
                   f"postcode = {q(z['postcode'])}, gemeente = {q(z['gemeente'])}, bijgewerkt_op = now(), "
                   f"bijgewerkt_door = {q(DOOR)} where id = {q(aid)}::uuid and straat = '' and huisnummer = '' "
                   f"and postcode = '' and gemeente = '' returning id), "
                   f"f as (update kern.firma set adres_id = {q(aid)}::uuid where code = {q(code)} and adres_id is null "
                   f"returning code) select json_build_object('adres', (select count(*) from u), "
                   f"'firma', (select count(*) from f))") or {}
        uit.append(f"{code}: adres van de zetel uit de KBO gezet" if res.get("firma") == 1
                   else f"{code}: niet gekoppeld (intussen gewijzigd?)")
    return uit


if __name__ == "__main__":
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "koppelingen"))
    import organisatie
    regels = vul(organisatie._psql, schrijf="--schrijf" in sys.argv[1:])
    print("\n".join(regels))
    compleet = S.laad_kern()
    print("kern compleet voor Bouw:", "ja" if compleet else "nee")
    sys.exit(0 if compleet else 1)          # Codex (controle 11): de uitrol stopt als kern onvolledig blijft
