#!/usr/bin/env python3
"""BA-plannen van H-Architects in Dropbox, voor De Tekenaar op de Mac. Alleen lezen.

De runner van De Tekenaar (tekenaar.py) draait op de Mac, waar zijn gereedschap staat. Die Mac heeft geen
Dropbox-sleutel, en zijn lokale Dropbox toont online-only bestanden als 0 bytes. Daarom vraagt de runner via ssh aan
dit script op de VM wat er in de twee projectmappen staat, en haalt hij de PDF's hier op, met het token van de stack
(koppelingen/bronnen.py). Er komt geen sleutel op de Mac.

    ba_plannen.py lijst      stdin: {"cursors": {"standaard": c, "light": c}} (zonder cursor: alles opnieuw)
                             stdout: {"versie", "cursors", "wijzigingen": [...], "volledig": {...}}; de wijzigingen
                             in de volgorde van Dropbox: {"soort": "bestand", id, pad, hash, ...} of {"soort": "weg", pad}
    ba_plannen.py haal <id>  de PDF op stdout; alleen een BA_*.pdf onder een van de twee projectmappen
    ba_plannen.py versie     de versie van dit script, zodat de Mac weet of de VM bij is

Alleen files/list_folder, files/list_folder/continue, files/get_metadata en files/download: nooit schrijven,
verplaatsen, delen of verwijderen.
"""
import json
import os
import re
import sys
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bronnen  # noqa: E402

VERSIE = "1"
BASISSEN = {"standaard": "/Work All/01. H-A WORK/0 H-A Standaard projects",
            "light": "/Work All/01. H-A WORK/0 H-A Light projects"}
MAX_BYTES = 80_000_000
MAX_PAGINAS = 1000          # 2000 per pagina: twee miljoen items, ruim boven de 170.000 van oktober 2026
ID = re.compile(r"^id:[A-Za-z0-9_-]{6,}$")


def is_ba_pdf(naam):
    n = (naam or "").lower()
    return n.startswith("ba_") and n.endswith(".pdf")


def onder_basis(pad_lower):
    return any((pad_lower or "").startswith(b.lower() + "/") for b in BASISSEN.values())


def bestand(e):
    return {"soort": "bestand", "id": e["id"], "pad": e.get("path_display") or e.get("path_lower"), "hash": e.get("content_hash"),
            "grootte": e.get("size"), "gewijzigd": e.get("server_modified"), "rev": e.get("rev")}


def lijst(cursors, rpc=None):
    """Alles wat sinds de cursor veranderde, per basismap; zonder (bruikbare) cursor de volledige lijst. Een cursor die
    Dropbox weigert (409, bijvoorbeeld reset), geeft ook de volledige lijst: die is altijd juist."""
    rpc = rpc or bronnen._rpc
    uit = {"versie": VERSIE, "cursors": {}, "wijzigingen": [], "volledig": {}}
    for sleutel, basis in BASISSEN.items():
        antwoord, volledig = None, False
        if cursors.get(sleutel):
            try:
                antwoord = rpc("files/list_folder/continue", {"cursor": cursors[sleutel]})
            except urllib.error.HTTPError as e:
                if e.code != 409:
                    raise
        if antwoord is None:
            antwoord = rpc("files/list_folder", {"path": basis, "recursive": True, "limit": 2000})
            volledig = True
            if antwoord is None:
                raise RuntimeError(f"projectmap {sleutel} niet gevonden in Dropbox")
        for _ in range(MAX_PAGINAS):
            if not isinstance(antwoord, dict) or not isinstance(antwoord.get("entries"), list) \
                    or type(antwoord.get("has_more")) is not bool or not antwoord.get("cursor"):
                raise RuntimeError(f"projectmap {sleutel}: onvolledige lijst van Dropbox")
            for e in antwoord["entries"]:
                if e.get(".tag") == "file" and is_ba_pdf(e.get("name")):
                    uit["wijzigingen"].append(bestand(e))
                elif e.get(".tag") == "deleted" and (is_ba_pdf(e.get("name")) or "." not in (e.get("name") or ".")):
                    # een weggehaald BA-plan of een weggehaalde map (verwijderd of verplaatst); andere bestanden niet
                    uit["wijzigingen"].append({"soort": "weg", "pad": e.get("path_lower") or ""})
            if not antwoord["has_more"]:
                break
            antwoord = rpc("files/list_folder/continue", {"cursor": antwoord["cursor"]})
        else:
            raise RuntimeError(f"projectmap {sleutel}: meer dan {MAX_PAGINAS} pagina's; niet volledig gelezen")
        uit["cursors"][sleutel] = antwoord["cursor"]
        uit["volledig"][sleutel] = volledig
    return uit


def haal(ident, rpc=None, download=None):
    """De inhoud van een BA-plan, na controle dat het een BA_*.pdf onder een projectmap is."""
    rpc, download = rpc or bronnen._rpc, download or bronnen.download
    if not ID.match(ident or ""):
        raise ValueError("geen Dropbox-id")
    meta = rpc("files/get_metadata", {"path": ident})
    if not meta or meta.get(".tag") != "file" or not is_ba_pdf(meta.get("name")) or not onder_basis(meta.get("path_lower")):
        raise PermissionError("geen BA-plan in de projectmappen")
    if (meta.get("size") or 0) > MAX_BYTES:
        raise ValueError("bestand groter dan de grens")
    return download(meta["path_lower"], maximum=MAX_BYTES)


def main(argv):
    if argv[:1] == ["versie"]:
        print(VERSIE)
        return 0
    if not bronnen.dropbox_beschikbaar():
        print("Dropbox-sleutels van de stack ontbreken", file=sys.stderr)
        return 3
    if argv[:1] == ["lijst"]:
        invoer = sys.stdin.read().strip()
        cursors = (json.loads(invoer).get("cursors") or {}) if invoer else {}
        json.dump(lijst(cursors), sys.stdout, ensure_ascii=False)
        return 0
    if argv[:1] == ["haal"] and len(argv) == 2:
        try:
            data = haal(argv[1])
        except (ValueError, PermissionError) as e:
            print(f"{type(e).__name__}: {e}", file=sys.stderr)
            return 4          # geen BA-plan (meer) onder de projectmappen: de Mac schrapt het uit zijn wachtrij
        sys.stdout.buffer.write(data)
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
