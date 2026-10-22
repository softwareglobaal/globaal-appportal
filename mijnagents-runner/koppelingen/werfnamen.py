"""De naamvormen van Mehdi's eigen bezoekmateriaal: één regel voor voorbereider en schrijver.

Alleen de exacte naamvormen die zijn eigen hulpmiddelen maken (gemeten op alle live bezoekmappen,
16-10-2026): de Plaudwacht en de skill ("transcript.txt", "transcript.docx", "00 verslag.md"), de
iCloud-wacht ("00 fotos.md") en de Plaud-export ("05-07 <titel>-transcript.txt|docx",
"20260820 2173 <titel>-transcript.txt", "2026-06-16 Plaud transcript.txt"). Een bestand van derden met
"transcript" ergens in de naam ("derden-transcript.txt") valt erbuiten (CX3-9, CX5-4).

Waarom een eigen module (17-10-2026): de voorbereider kende alleen "transcript.txt" en zette W6 op
"ontbreekt" voor 2173 werfbezoek 4, terwijl de schrijver het Plaud-exporttranscript in dezelfde map
wel las. Twee regels voor hetzelfde gegeven geven een verkeerde stand.
"""
import re

EIGEN_NAMEN = (re.compile(r"(transcript\.(txt|docx)|00 verslag\.md|00 fotos\.md)", re.I),
               re.compile(r"\d{2}-\d{2} .+-transcript\.(txt|docx)", re.I),
               re.compile(r"\d{8} \d{4} .+-transcript\.(txt|docx)", re.I),
               re.compile(r"\d{4}-\d{2}-\d{2} plaud transcript\.(txt|docx)", re.I))


def eigen_tekst(naam):
    """Een eigen tekstbestand van het bezoek: transcript, 00 verslag.md of 00 fotos.md."""
    return any(p.fullmatch(naam.strip()) for p in EIGEN_NAMEN)


def eigen_transcript(naam):
    """Een eigen transcript (niet het verslag of het fotomanifest), in een van de naamvormen hierboven."""
    n = naam.strip()
    return eigen_tekst(n) and "transcript" in n.lower()


def vertrouwde_transcriptkop(tekst):
    """Een generieke transcript.txt is alleen eigen met Plaud-id of skill-herkomst in de kop."""
    kop = "\n".join(str(tekst).splitlines()[:8])
    return bool(re.search(r"(?im)^\s*plaud_id\s*:\s*[\w-]{8,}\s*$", kop)
                or (re.search(r"(?im)^\s*dossier\s*:\s*\d{4}\s*$", kop)
                    and re.search(r"(?im)^\s*bezoekmap\s*:\s*/\S+", kop))
                or re.search(r"(?im)^\s*(?:bron|gemaakt door)\s*:\s*.*(?:werfverslag.skill|skill werfverslag|plaud)", kop)
                or re.search(r"(?im)^\s*#\s*(?:werfverslag.skill|skill werfverslag)", kop))
