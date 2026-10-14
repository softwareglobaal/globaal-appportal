"""Volledige tekstsegmenten en deterministische feiten, zonder provider of opslag."""
from copy import deepcopy
import hashlib
import json

VERSIE = "werfextractie-1"
SEGMENT_TEKENS = 12000


class BronLeesFout(RuntimeError):
    """Een bron is niet volledig gelezen; betaalde verwerking mag nog niet starten."""


def sha256(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def segmenten(bron, maximum=SEGMENT_TEKENS):
    """Alle tekens eenmaal, met exclusieve eindpositie. Niets stil afknippen."""
    tekst = bron.get("tekst", "")
    if bron.get("leesfout") or not tekst.strip():
        raise BronLeesFout(f"{bron['naam']}: {bron.get('leesfout') or 'geen leesbare tekst; OCR of transcript nodig'}")
    if maximum < 1:
        raise ValueError("segmentgrootte moet positief zijn")
    aantal = (len(tekst) + maximum - 1) // maximum
    return [{"naam": bron["naam"], "bron_hash": bron.get("sha256") or sha256(tekst),
             "segment": i + 1, "segmenten": aantal, "van": van, "tot": min(van + maximum, len(tekst)),
             "tekst": tekst[van:van + maximum]} for i, van in enumerate(range(0, len(tekst), maximum))]


def manifest(teksten, fotos, opnames):
    return ([{"naam": b["naam"], "soort": "document", "sha256": b.get("sha256") or sha256(b.get("tekst", "")),
              "file_id": b.get("file_id", ""), "pad": b.get("pad", ""),
              "bytes": b.get("bytes"),
              "rev": b.get("rev", ""), "tekens": len(b.get("tekst", "")), "leesfout": b.get("leesfout", ""),
              "extractor": VERSIE} for b in teksten]
            + [{"naam": f["naam"], "soort": "foto", "rev": f.get("rev", ""), "provider_hash": f.get("content_hash", ""),
                "file_id": f.get("file_id", ""), "pad": f.get("pad", ""),
                "grootte": f.get("grootte", 0), "beeldanalyse": "niet uitgevoerd"} for f in fotos]
            + [{"naam": n, "soort": "opname", "audioanalyse": "niet uitgevoerd; transcript is de tekstbron"} for n in opnames])


def _uniek(items):
    gezien, uit = set(), []
    for item in items:
        sleutel = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if sleutel not in gezien:
            gezien.add(sleutel)
            uit.append(deepcopy(item))
    return uit


def voeg_samen(resultaten):
    """Behoud tegenstrijdige feiten en hun bron; maak het conflict zichtbaar."""
    uit = {"gegevens": [], "situatie": "", "onderdelen": [], "acties": [], "ontbreekt": [], "verslagtype_voorstel": "werfverslag"}
    for veld in ("gegevens", "onderdelen", "acties", "ontbreekt"):
        uit[veld] = _uniek([item for resultaat in resultaten for item in resultaat.get(veld, [])])
    # 'Niet gevonden' in segment A mag geen bewezen feit uit segment B verdringen.
    bewezen = {g["veld"].strip().casefold() for g in uit["gegevens"] if g["zekerheid"] != "ontbreekt"}
    uit["gegevens"] = [g for g in uit["gegevens"] if g["zekerheid"] != "ontbreekt" or g["veld"].strip().casefold() not in bewezen]
    per_veld = {}
    for g in uit["gegevens"]:
        if g["zekerheid"] != "ontbreekt":
            per_veld.setdefault(g["veld"].strip().casefold(), set()).add(g["waarde"].strip().casefold())
    for veld, waarden in sorted(per_veld.items()):
        if len(waarden) > 1:
            uit["ontbreekt"].append(f"Tegenstrijdige bronwaarden voor {veld}: architect moet kiezen; alle herkomsten blijven bewaard")
            for g in uit["gegevens"]:
                if g["veld"].strip().casefold() == veld:
                    g["zekerheid"] = "na te kijken"
    uit["situatie"] = "\n\n".join(_uniek([r["situatie"] for r in resultaten if r.get("situatie", "").strip()]))
    voorstellen = {r.get("verslagtype_voorstel", "werfverslag") for r in resultaten}
    if len(voorstellen) == 1:
        uit["verslagtype_voorstel"] = voorstellen.pop()
    elif len(voorstellen) > 1:
        uit["ontbreekt"].append("Bronnen stellen verschillende verslagtypes voor; Mehdi beslist in Keuzes")
    return uit


def menselijke_laag(resultaat, vorige):
    """Alleen expliciet menselijke feiten behouden, geen oude brede AI-voorbereiding."""
    patches = list((vorige or {}).get("menselijke_correcties") or [])
    patches += [g for g in (vorige or {}).get("gegevens", []) if isinstance(g, dict)
                and (g.get("menselijk") is True or g.get("herkomst_soort") == "mens" or g.get("bron") in ("Mehdi", "menselijke correctie"))]
    patches = [deepcopy(g) for g in patches if isinstance(g, dict) and isinstance(g.get("veld"), str) and isinstance(g.get("waarde"), str)]
    for g in patches:
        g.update(menselijk=True, bron=g.get("bron") or "menselijke correctie", zekerheid=g.get("zekerheid") or "zeker")
    velden = {g["veld"].strip().casefold() for g in patches}
    uit = deepcopy(resultaat)
    uit["gegevens"] = [g for g in uit["gegevens"] if g["veld"].strip().casefold() not in velden] + _uniek(patches)
    if patches:
        uit["menselijke_correcties"] = _uniek(patches)
    return uit


def valideer(data, schema, pad="resultaat"):
    """De gebruikte toolschema's volledig toetsen zonder extra runtimeafhankelijkheid."""
    typ = schema.get("type")
    typen = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int, "number": (int, float)}
    if typ in typen and (not isinstance(data, typen[typ]) or typ in ("integer", "number") and isinstance(data, bool)):
        raise ValueError(f"{pad}: verwacht {typ}")
    if "enum" in schema and data not in schema["enum"]:
        raise ValueError(f"{pad}: ongeldige keuzewaarde")
    if isinstance(data, dict):
        if "properties" in schema:
            onbekend = set(data) - set(schema["properties"])
            if onbekend:
                raise ValueError(f"{pad}: onverwachte velden {', '.join(sorted(onbekend))}")
        for veld in schema.get("required", []):
            if veld not in data:
                raise ValueError(f"{pad}: verplicht veld {veld} ontbreekt")
        for veld, subschema in schema.get("properties", {}).items():
            if veld in data:
                valideer(data[veld], subschema, f"{pad}.{veld}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            valideer(item, schema.get("items", {}), f"{pad}[{i}]")
    return data
