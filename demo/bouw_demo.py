"""Bouwt de kennisbank die de publieke demo laat zien.

    python bouw_demo.py <document.pdf> [--titel "Naam op het scherm"]
    python bouw_demo.py --ocr-cache <map> [--titel "..."]

Levert data/demo.db op. Die database is het enige wat de demo nodig heeft; de
container koppelt hem aan als volume, dus een ander demodocument vraagt geen
nieuwe image en geen herstart van iets anders.

Twee bronnen. Een PDF met tekstlaag gaat er rechtstreeks in. Een map met
OCR-delen (uit ingestie/ocr.py) is de betere route, ook voor een document dat
al tekst heeft: het model wijst per blok aan wat titel, koptekst en voettekst
is, en op die typering leunt de indelingsherkenning. Zonder die typering moet
structuur.py het uit lettergroottes raden, en bij een wettekst zonder echte
inhoudsopgave levert dat vrijwel niets op.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

BASIS = Path(__file__).resolve().parent
sys.path.insert(0, str(BASIS))

from kennisbank import knippen, ocrbron, pdfbron, structuur as S, vectoren  # noqa: E402
from kennisbank.opslag import Kennisbank  # noqa: E402


def _bladen_uit_pdf(pdf: Path):
    verkenning = pdfbron.verken(pdf)
    if verkenning.fout:
        raise SystemExit(f"kan het bestand niet lezen: {verkenning.fout}")
    if not verkenning.heeft_tekstlaag:
        raise SystemExit(
            f"{pdf.name} is een scan zonder tekstlaag ({verkenning.bladzijden} "
            "bladzijden). Laat hem eerst met OCR uitlezen, of kies een "
            "document dat digitaal is opgemaakt.")
    print(f"{verkenning.bladzijden} bladzijden, tekstlaag aanwezig")
    return pdfbron.laad(pdf)


def bouw(bron: Path, uit: Path, titel: str, bestandsnaam: str,
         uit_ocr: bool) -> None:
    if uit_ocr:
        bladen = ocrbron.laad_uit_cache(bron)
        soorten = {b.soort for bl in bladen for b in bl.blokken}
        print(f"{len(bladen)} bladzijden uit de OCR-cache, "
              f"bloksoorten: {sorted(soorten)}")
    else:
        bladen = _bladen_uit_pdf(bron)

    st = S.analyseer(bladen)
    gedrukt = {}
    if st.ijking.verschuiving is not None:
        gedrukt = {b.fysiek: b.fysiek - st.ijking.verschuiving
                   for b in bladen if b.fysiek > st.ijking.voorwerk_tot}
    print(f"indeling: {len(st.secties)} secties, {st.trefkans:.0%} van de "
          "inhoudsopgave teruggevonden")

    overslaan = set(st.inhoudsopgave_paginas)
    fragmenten = knippen.knip(bladen, st.secties, overslaan=overslaan,
                              gedrukt_van=gedrukt)
    if not fragmenten:
        raise SystemExit("geen fragmenten; is dit wel een tekstdocument?")
    dek = knippen.dekking(bladen, fragmenten, overslaan=overslaan)

    lengtes = sorted(len(f.tekst.split()) for f in fragmenten
                     if f.soort == "tekst")
    print(f"{len(fragmenten)} fragmenten, mediaan {lengtes[len(lengtes) // 2]} "
          f"woorden, dekking {dek['aandeel']:.1%}")

    vecs = vectoren.embed([f.met_context for f in fragmenten])

    if uit.exists():
        uit.unlink()
    bank = Kennisbank(uit)
    bank.leg_vast(
        doc_id="demo", titel=titel, bestandsnaam=bestandsnaam,
        bladzijden=len(bladen),
        aangemaakt=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        trefkans=st.trefkans, verschuiving=st.ijking.verschuiving,
        dekking=dek["aandeel"], verwerking=1,
        strategie="woordband" + (" na OCR" if uit_ocr else " uit tekstlaag"),
        meta={"inhoudsopgave_paginas": st.inhoudsopgave_paginas,
              "band": [knippen.MIN_WOORDEN, knippen.MAX_WOORDEN]})
    bank.schrijf_secties(st.secties)
    bank.schrijf_fragmenten(fragmenten, vecs)
    bank.sluit()
    print(f"klaar: {uit}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pdf", type=Path, nargs="?")
    p.add_argument("--ocr-cache", type=Path, dest="ocr_cache")
    p.add_argument("--uit", type=Path, default=BASIS / "data" / "demo.db")
    p.add_argument("--titel", default="")
    p.add_argument("--bestandsnaam", default="")
    a = p.parse_args()
    if bool(a.pdf) == bool(a.ocr_cache):
        p.error("geef of een PDF of --ocr-cache, niet allebei en niet geen van beide")
    bron = a.ocr_cache or a.pdf
    a.uit.parent.mkdir(parents=True, exist_ok=True)
    bouw(bron, a.uit, a.titel or bron.stem,
         a.bestandsnaam or (a.pdf.name if a.pdf else bron.name),
         uit_ocr=bool(a.ocr_cache))
