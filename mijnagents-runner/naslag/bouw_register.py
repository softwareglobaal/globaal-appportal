"""Bouw het bronnenregister uit de lokale pdf's en de kennisbankinventaris."""

import argparse
import json
import os
import re
from pathlib import Path

HIER = Path(__file__).resolve().parent
INVENTARIS = HIER.parent / "docs" / "kennisbank-inventaris.md"
REGISTER = HIER / "bronnenregister.json"
PDF_BASIS = Path(os.environ.get("NASLAG_PDF", "~/appportal/mijnagents-data/naslag/pdf")).expanduser()
MAPPEN = ("tv", "dimensionering", "meetstaten", "keuring")


def sleutel_en_titel(bestand, mapnaam):
    stam = Path(bestand).stem
    naam = re.sub(r"^\d{5}_nl_unprotected_", "", stam, flags=re.I)
    patronen = (
        (r"TVN?[_ ]?(\d{2,3}(?:\.\d+)?)(?:[_ ]?(Add\d+))?", "TV"),
        (r"(?:WTCB_)?Digest[_ ]?(?:nr[_ ]?)?(\d+(?:_\d+)?)", "DIGEST"),
        (r"TV_RECAP[_ ]?(\d+)", "RECAP"),
        (r"WTCB_Rapport[_ ]?(\d+)", "WTCB_R"),
        (r"Meetstaat[_ ]?(\d+(?:_\d+)*)", "MEETSTAAT_"),
    )
    for patroon, voorvoegsel in patronen:
        m = re.search(patroon, naam, re.I)
        if m:
            nummer = m.group(1).replace("_", "_")
            sleutel = voorvoegsel + nummer + (("_" + m.group(2).upper()) if m.lastindex and m.lastindex > 1 and m.group(2) else "")
            titel = naam[m.end():].strip(" _.;-") or naam
            return sleutel, titel
    if mapnaam == "keuring":
        return "VLARIO_" + re.sub(r"[^A-Z0-9]+", "_", naam.upper()).strip("_"), naam.replace("-", " ")
    return re.sub(r"[^A-Z0-9]+", "_", naam.upper()).strip("_"), naam.replace("_", " ")


def inventarisgegevens(pad=INVENTARIS):
    inhoud = Path(pad).read_text(encoding="utf-8")
    hoofdstuk = inhoud.split("### 4.1 ", 1)[1].split("### 4.2 ", 1)[0]
    koppeling = {}
    for regel in hoofdstuk.splitlines():
        if not regel.startswith("| ") or regel.startswith("| Fase") or regel.startswith("|---"):
            continue
        cellen = [c.strip() for c in regel.strip().strip("|").split("|")]
        if len(cellen) < 3:
            continue
        fases = [x.strip() for x in cellen[0].split(",")]
        punt = cellen[1]
        bron = cellen[2]
        verwijzingen = re.findall(r"\bTV(?:_RECAP)?[_ ]?(\d{2,3}(?:\.\d+)?)(?:\s*\+\s*(Add\d+))?|\bDigest(?:s)?\s+(\d+(?:\s*,\s*\d+)*)|\bWTCB_Rapport[_ ]?(\d+)", bron, re.I)
        sleutels = []
        for tv, add, digest, rapport in verwijzingen:
            if tv:
                sleutel = ("RECAP" if "TV_RECAP" in bron and "TV " not in bron else "TV") + tv
                sleutels.append(sleutel)
                if add:
                    sleutels.append(sleutel + "_" + add.upper())
            if digest:
                sleutels.extend("DIGEST" + n.strip() for n in digest.split(","))
            if rapport:
                sleutels.append("WTCB_R" + rapport)
        if "TV_RECAP_17" in bron:
            sleutels.append("RECAP17")
        if "TV 240" in bron:
            sleutels.extend(("TV240_ADD1", "TV240_ADD2"))
        if "meetstaten van gebouwen" in bron:
            sleutels.append("MEETSTAAT_*")
        if "keuring richtlijnen/" in bron:
            sleutels.append("VLARIO_*")
        for sleutel in sleutels:
            doel = koppeling.setdefault(sleutel, {"fases": [], "werfpunten": []})
            for fase in fases:
                if fase and fase not in doel["fases"]:
                    doel["fases"].append(fase)
            if punt not in doel["werfpunten"]:
                doel["werfpunten"].append(punt)
    jaren = {}
    for regel in inhoud.splitlines():
        m = re.match(r"\| (TVN?[_ ]?\d+(?:\.\d+)?|WTCB_Digest nr\. \d+|WTCB_Rapport_\d+|Meetstaat_\d+(?:_\d+)*)\b[^|]*\|\s*([^|]+)", regel)
        if m:
            sleutel, _ = sleutel_en_titel(m.group(1) + ".pdf", "tv")
            jaar = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", m.group(2))
            if jaar:
                jaren[sleutel] = int(jaar.group(1))
    rapportjaar = re.search(r"\| WTCB_Rapport_20 [^|]*\|[^|]*?((?:19|20)\d{2})", inhoud)
    if rapportjaar:
        jaren["WTCB_R20"] = int(rapportjaar.group(1))
    # Hoofdstuk 4.2 noemt expliciet vervangen TV's. Een oud document krijgt
    # daarnaast alleen de status verouderd als het uit de periode voor 2010 komt.
    oud = inhoud.split("### 4.2 ", 1)[1].split("### 4.3 ", 1)[0]
    vervangen = {"TV" + nummer for groep in re.findall(r"\bTV\s+(\d{2,3}(?:/\d{2,3})?)\s*\(", oud.split("- Ouder dan 2015", 1)[0])
                for nummer in groep.split("/")}
    return koppeling, jaren, vervangen, inhoud


def _inventaris_bestanden(inhoud):
    """Voor een checkout zonder server-pdf's: expliciet genoemde pdf-namen."""
    resultaat = []
    sectie = None
    for regel in inhoud.splitlines():
        if regel.startswith("### Technische Voorlichtingen:"):
            sectie = "tv"
        elif regel.startswith("### Buildwise Documenten / dimensioneringsmethodes"):
            sectie = "dimensionering"
        elif regel.startswith("### Buildwise Documenten / meetstaten"):
            sectie = "meetstaten"
        elif regel.startswith("### keuring richtlijnen"):
            sectie = "keuring"
        elif regel.startswith("### "):
            sectie = None
        if sectie is None:
            continue
        if regel.startswith("| "):
            kandidaat = regel.split("|", 2)[1].strip()
            if kandidaat.lower().endswith(".pdf"):
                resultaat.append((sectie, kandidaat))
        elif sectie == "tv" and regel.startswith("TVN_"):
            for kandidaat in re.findall(r"(TVN_.*?\.pdf)\s*\([^)]*MB\)", regel):
                resultaat.append((sectie, kandidaat.strip()))
    return list(dict.fromkeys(resultaat))


def maak_register(pdf_basis=PDF_BASIS, inventaris=INVENTARIS, fallback=False):
    koppeling, jaren, vervangen, inhoud = inventarisgegevens(inventaris)
    basis = Path(pdf_basis).expanduser()
    ontbrekende = [mapnaam for mapnaam in MAPPEN if not (basis / mapnaam).is_dir()]
    if ontbrekende and not (fallback and len(ontbrekende) == len(MAPPEN)):
        raise FileNotFoundError(f"naslag-pdfmappen ontbreken onder {basis}: {', '.join(ontbrekende)}")
    bestanden = [(mapnaam, p.name) for mapnaam in MAPPEN for p in sorted((basis / mapnaam).glob("*.pdf"))]
    if not bestanden and fallback:
        bestanden = _inventaris_bestanden(inhoud)
    if not bestanden:
        raise FileNotFoundError(f"geen pdf's gevonden onder {basis}; register niet overschreven")
    records = []
    gebruikte = set()
    for mapnaam, bestand in bestanden:
        sleutel, titel = sleutel_en_titel(bestand, mapnaam)
        basis_sleutel = sleutel
        if sleutel in gebruikte:
            aanvulling = re.sub(r"[^A-Z0-9]+", "_", titel.upper()).strip("_")[:45]
            sleutel = f"{sleutel}_{aanvulling}" if aanvulling else f"{sleutel}_2"
            teller = 2
            while sleutel in gebruikte:
                teller += 1
                sleutel = f"{basis_sleutel}_{aanvulling}_{teller}"
        gebruikte.add(sleutel)
        match = koppeling.get(basis_sleutel, koppeling.get("MEETSTAAT_*" if mapnaam == "meetstaten" else "VLARIO_*" if mapnaam == "keuring" else "", {}))
        jaar_in_naam = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", bestand)
        jaar = jaren.get(basis_sleutel) or (int(jaar_in_naam.group(1)) if jaar_in_naam else None)
        vervangt = []
        for clausule in re.findall(r"(?:vervangt|herziening van|vervangen de)[^)]*", bestand, re.I):
            if "TV" not in clausule.upper():
                continue
            na_tv = re.split(r"TV(?:'s)?", clausule, maxsplit=1, flags=re.I)[-1]
            vervangt.extend("TV" + n for n in re.findall(r"(?<!\d)\d{2,3}(?!\d)", na_tv))
        vervangt = list(dict.fromkeys(vervangt))
        if mapnaam == "keuring":
            uitgever, licentie = "VLARIO", "vlario"
        elif basis_sleutel.startswith(("DIGEST", "WTCB_R", "MEETSTAAT")):
            uitgever, licentie = "WTCB", "buildwise"
        else:
            uitgever, licentie = ("WTCB" if jaar and jaar < 2022 else "Buildwise"), "buildwise"
        status = "ongekend" if not match else "verouderd" if (basis_sleutel in vervangen or basis_sleutel.startswith("TV") and jaar and jaar < 2010 or basis_sleutel == "DIGEST1") else "geldig"
        records.append({"sleutel": sleutel, "titel": titel, "map": mapnaam, "bestand": bestand,
                        "jaar": jaar, "uitgever": uitgever, "vervangt": vervangt,
                        "fases": match.get("fases", []), "werfpunten": match.get("werfpunten", []),
                        "licentie": licentie, "status": status})
    return records


def schrijf_register(pdf_basis=PDF_BASIS, inventaris=INVENTARIS, uitvoer=REGISTER, fallback=False):
    records = maak_register(pdf_basis, inventaris, fallback=fallback)
    pad = Path(uitvoer)
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=PDF_BASIS)
    parser.add_argument("--inventaris", type=Path, default=INVENTARIS)
    parser.add_argument("--uitvoer", type=Path, default=REGISTER)
    parser.add_argument("--uit-inventaris", action="store_true", help="gebruik bestandsnamen uit inventaris als de pdf-map ontbreekt")
    args = parser.parse_args()
    records = schrijf_register(args.pdf, args.inventaris, args.uitvoer, fallback=args.uit_inventaris)
    print(f"{len(records)} bronnen in {args.uitvoer}")
