"""Zoektaken voor De Plaudwacht: een opname zoeken voor een bezoek en het transcript in de bezoekmap
leveren (verbeteropdracht v1.0, §2 en §8).

De taken komen van het Commandocentrum (uniek cc:<..>:plaud-wacht, met van_tijd en tot_tijd) en van
de werfverslagvoorbereider (uniek werf:<nummer>:<datum>:plaud-wacht, alleen een datum). Uitkomst:

    gevonden              één opname met transcript past; het transcript wordt geleverd
    wacht_op_transcript   één opname past, maar het transcript bestaat (nog) niet
    niet_gevonden         geen opname past
    conflict              meer dan één opname past, of de opname wijst naar een ander dossier

Dezelfde dag alleen is nooit genoeg: bij een taak met alleen een datum moet de opname zelf bewijs voor
het dossier hebben (titel, openingszin, overlappende afspraak of kop); met een tijdvenster bevestigt het
opnametijdstip.

Het schrijfpad komt uit de taak zelf (de gevalideerde bezoekrij), nooit uit een transcriptkop: een
pad in een transcript is een aanwijzing, geen autorisatie. Bij de klassieke bezoekmap controleren
we firma, dossier, bezoekdatum en taak-id. Bij een TKN-dossiermap controleren we daarnaast het
mapnummer, de Plaud-submap en de vaste transcriptnaam. Een bestaande kopie telt pas als geleverd
als de Plaud-id in de kop overeenkomt. Een ander bestand wordt nooit overschreven.
"""
import hashlib
import json
import re
from datetime import date, datetime, timedelta

from context import BRUSSEL
import dossier as ds
import verslagsoorten as vs

VOOR = timedelta(minutes=30)
NA = timedelta(minutes=60)
HA_WORK = "/Work All/01. H-A WORK/"


def inhoud_van(taak):
    i = taak.get("inhoud") or {}
    if isinstance(i, str):
        try:
            i = json.loads(i) if i.startswith("{") else {}
        except ValueError:
            i = {}
    return i if isinstance(i, dict) else {}


def verslagsoort(taak):
    i = inhoud_van(taak)
    return i.get("verslagsoort") or ("werfverslag" if taak.get("van") == "werfverslag-voorbereider" else "")


AFDELING_FIRMA = {"h-architects": "HARC", "unabo": "UNAB", "tkn": "TKNB", "harmoniebouw": "HARM", "contrax": "CONT", "elevait": "ELEV"}


def bewijs_van(taak, soorten):
    """Het dossierbewijs dat een gevalideerde zoektaak geeft: (firma, nummer) of None.
    Alleen een projectnummer telt; een klantnaam als dossier is geen nummer."""
    i = inhoud_van(taak)
    nummer = str(i.get("dossier") or "")
    if not re.fullmatch(r"\d{4,6}", nummer):
        return None
    soort = verslagsoort(taak)
    s = soorten.get(soort) or {}
    if s.get("submappen") and len(nummer) == 4 and nummer in re.findall(
            r",\s*(\d{4})\b", str(i.get("adres") or "")):
        return None
    afdeling = "h-architects" if soort == "werfverslag" else s.get("afdeling", "")
    agenda_firma = i.get("firma") if s.get("submappen") and i.get("plaud_doelmap") else None
    firma = agenda_firma if isinstance(agenda_firma, str) and agenda_firma in ds.FIRMA_AFDELING else AFDELING_FIRMA.get(afdeling)
    return (firma, nummer) if firma else None


def _tijd(datum, tijd):
    if not tijd:
        return None
    t = str(tijd)
    try:
        if "T" in t:
            d = datetime.fromisoformat(t.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=BRUSSEL)
        return datetime.fromisoformat(f"{datum}T{t[:5]}").replace(tzinfo=BRUSSEL)
    except ValueError:
        return None


def valideer_bezoekmap(taak, soorten):
    """(ok, reden). soorten = verslagsoorten.SOORTEN."""
    i = inhoud_van(taak)
    bezoekmap = i.get("bezoekmap") or ""
    if not isinstance(bezoekmap, str):
        return False, "bezoekmap is geen geldig Dropbox-pad"
    pad = bezoekmap.rstrip("/")
    datum = i.get("datum") or ""
    dossier = str(i.get("dossier") or "")
    if not taak.get("id"):
        return False, "taak zonder id"
    if not pad.startswith("/") or ".." in pad.split("/") or "\x00" in pad:
        return False, "bezoekmap is geen geldig Dropbox-pad"
    soort = verslagsoort(taak)
    s = soorten.get(soort) or {}
    if s.get("submappen"):
        if taak.get("van") != "commandocentrum":
            return False, "TKN-doel vraagt een taak van het Commandocentrum"
        mapnummer = str(i.get("mapnummer") or "")
        if not re.fullmatch(r"\d{4,6}", mapnummer) or not re.fullmatch(r"\d{4,6}", dossier):
            return False, "TKN-doel vraagt een geldig mapnummer en dossiernummer"
        if len(dossier) == 4 and dossier in re.findall(r",\s*(\d{4})\b", str(i.get("adres") or "")):
            return False, "TKN-dossiernummer is de postcode van het bezoekadres"
        basissen = s.get("basismappen") or []
        if pad != bezoekmap or not any(vs.tkn_pad(pad, basis) == mapnummer for basis in basissen):
            return False, "bezoekmap is geen TKN-dossiermap met dit mapnummer"
        doelmap = i.get("plaud_doelmap") or ""
        if not isinstance(doelmap, str) or not doelmap.startswith(pad + "/") or "/" in doelmap[len(pad) + 1:]:
            return False, "Plaud-doelmap ligt niet rechtstreeks onder de TKN-dossiermap"
        if vs.submap_sleutel(doelmap[len(pad) + 1:]) != "plaud":
            return False, "Plaud-doelmap is geen bekende Plaud-submap"
        try:
            if date.fromisoformat(datum).isoformat() != datum:
                raise ValueError
        except (TypeError, ValueError):
            return False, "bezoekdatum is geen ISO-datum"
        if i.get("transcriptnaam") != s["transcriptnaam"].format(datum=datum):
            return False, "transcriptnaam hoort niet bij de bezoekdatum"
        return True, ""
    if soort == "werfverslag":
        basissen = [HA_WORK]
    elif soort in soorten:
        basissen = [b.rstrip("/") + "/" for b in soorten[soort].get("basismappen") or []]
    else:
        return False, f"onbekende verslagsoort: {soort or 'leeg'}"
    if not any(pad.startswith(b) for b in basissen):
        return False, f"bezoekmap ligt buiten de mappen van {soort}"
    if re.fullmatch(r"\d{4,6}", dossier) and not any(re.match(rf"{dossier}(?!\d)", s) for s in pad.split("/")):
        return False, f"bezoekmap hoort niet bij dossier {dossier}"
    laatste = pad.split("/")[-1]
    if not datum or (datum not in laatste and datum.replace("-", "") not in laatste):
        return False, f"bezoekmap hoort niet bij de bezoekdag {datum}"
    return True, ""


def beoordeel(taak, opnames, beslissingen, bewijs=None):
    """opnames: contracten {plaud_id, start_utc, start_brussel, duur_minuten, transcript: {staat}}.
    beslissingen: plaud_id -> dossier.beslis-resultaat (voor de controle op een ander dossier).
    bewijs: plaud_id -> set van projectnummers uit eigen bewijs van de opname (titel, openingszin,
    overlappende afspraak, kop), nooit uit de zoektaak zelf of uit het model.

    Met van_tijd en tot_tijd bevestigt het opnametijdstip. Met alleen een datum moet de opname zelf
    bewijs voor het dossier hebben: dezelfde dag alleen is geen bevestiging (verbeteropdracht v1.0)."""
    bewijs = bewijs or {}
    i = inhoud_van(taak)
    datum = i.get("datum") or ""
    dossier = str(i.get("dossier") or "")
    van, tot = _tijd(datum, i.get("van_tijd")), _tijd(datum, i.get("tot_tijd"))
    dag = [o for o in opnames if o["start_brussel"][:10] == datum]
    if van and tot:
        kand = []
        for o in dag:
            s = datetime.fromisoformat(o["start_utc"].replace("Z", "+00:00"))
            e = s + timedelta(minutes=float(o.get("duur_minuten") or 0) or 1)
            if s < tot + NA and e > van - VOOR:
                kand.append(o)
        grond = "opnametijd overlapt het bezoek"
    else:
        kand = [o for o in dag if dossier and dossier in bewijs.get(o["plaud_id"], set())]
        grond = f"op de bezoekdag, met eigen bewijs voor dossier {dossier}"
        if not kand:
            reden = (f"op de bezoekdag {len(dag)} opname(s), geen met eigen bewijs voor dossier {dossier}; "
                     "dezelfde dag alleen is geen bevestiging") if dag else "geen opname op de bezoekdag"
            return {"uitkomst": "niet_gevonden", "reden": reden, "kandidaten": [o["plaud_id"] for o in dag]}
    eigen = []
    for o in kand:
        b = beslissingen.get(o["plaud_id"]) or {}
        if b.get("projectnummer") and dossier and b["projectnummer"] != dossier:
            continue                      # deze opname hoort aantoonbaar bij een ander dossier
        if dossier and bewijs.get(o["plaud_id"]) and dossier not in bewijs[o["plaud_id"]]:
            continue                      # eigen bewijs wijst alleen naar andere dossiers
        if b.get("conflict"):
            return {"uitkomst": "conflict", "reden": "de opname zelf heeft tegenstrijdig dossierbewijs", "kandidaten": [o["plaud_id"]]}
        if b.get("prive"):
            return {"uitkomst": "conflict", "reden": "de opname is als privé herkend; alleen Mehdi beslist", "kandidaten": [o["plaud_id"]]}
        eigen.append(o)
    if not eigen:
        return {"uitkomst": "niet_gevonden", "reden": "geen opname die past", "kandidaten": []}
    if len(eigen) > 1:
        return {"uitkomst": "conflict", "reden": "meer dan één opname past", "kandidaten": [o["plaud_id"] for o in eigen]}
    o = eigen[0]
    if (o.get("transcript") or {}).get("staat") != "aanwezig":
        return {"uitkomst": "wacht_op_transcript", "reden": grond, "kandidaten": [o["plaud_id"]], "plaud_id": o["plaud_id"]}
    return {"uitkomst": "gevonden", "reden": grond, "kandidaten": [o["plaud_id"]], "plaud_id": o["plaud_id"]}


def transcript_hash(tekst):
    return hashlib.sha256((tekst or "").encode("utf-8")).hexdigest()[:16]


def _kop(begin):
    uit = {}
    for regel in begin.splitlines()[:10]:
        if ":" in regel:
            k, _, v = regel.partition(":")
            uit[re.sub(r"[- ]", "_", k.strip().lower())] = v.strip()
    return uit


def lever(bezoekmap, plaud_id, tekst, dropbox, naam="transcript.txt", scan_alle=False):
    """Zet het transcript in de map en bevestig id én transcriptversie (nacontrole v1.1, P2-9).

    Bovenaan het bestand: `plaud_id:` en `transcript_hash:`. Uitkomst:
        al_geleverd    dit id met deze versie staat er al
        geleverd       nieuw bestand, nagelezen
        nieuwe_versie  dit id stond er met een andere versie; die blijft onaangeroerd en de nieuwe versie
                       komt ernaast als `<naam> versie <hash>.txt` (geen overschrijving zonder toestemming)
        conflict       er staat een transcript van een andere opname: niets geschreven
    In een gewone bezoekmap telt elk transcript*.txt; in een dossiermap alleen bestanden met dezelfde
    naamstam. Bij scan_alle telt elk .txt-bestand in de Plaud-submap, ook een handmatig opgeslagen
    transcript met een andere naam of kopindeling. Bestanden zonder deze Plaud-id blijven staan."""
    h = transcript_hash(tekst)
    kop = f"plaud_id: {plaud_id}\ntranscript_hash: {h}\n"
    stam = "transcript" if naam == "transcript.txt" else naam[:-4]
    oudere = False
    items = dropbox.lijst(bezoekmap, recursief=False)
    if scan_alle and items is None:
        return {"uitkomst": "conflict", "reden": "doelmap bestaat niet"}
    koplengte = 2000 if scan_alle else 600
    for e in items or []:
        bestaand = e.get("name") or ""
        if (e.get(".tag") == "file" and bestaand.lower().endswith(".txt")
                and (scan_alle or bestaand.lower().startswith(stam.lower()))):
            k = _kop(dropbox.download_kop(e["path_display"], koplengte).decode("utf-8", "replace"))
            if k.get("plaud_id") != plaud_id:
                if scan_alle:
                    continue
                return {"uitkomst": "conflict", "pad": e["path_display"], "reden": "er staat al een transcript van een andere opname"}
            if k.get("transcript_hash") == h or (scan_alle and not k.get("transcript_hash")):
                return {"uitkomst": "al_geleverd", "pad": e["path_display"], "transcript_hash": h}
            oudere = True
    doelnaam = f"{stam} versie {h[:6]}.txt" if oudere else naam
    pad = dropbox.upload(f"{bezoekmap}/{doelnaam}", (kop + "\n" + tekst).encode("utf-8"))
    controle = _kop(dropbox.download_kop(pad, koplengte).decode("utf-8", "replace"))
    if controle.get("plaud_id") != plaud_id or controle.get("transcript_hash") != h:
        raise RuntimeError("levering niet bevestigd: het bestand in de map is niet deze opname of niet deze versie")
    return {"uitkomst": "nieuwe_versie" if oudere else "geleverd", "pad": pad, "transcript_hash": h}
