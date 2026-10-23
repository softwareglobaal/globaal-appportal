#!/usr/bin/env python3
"""Tel uitsluitend expliciet gekozen WhatsApp-exports op Mehdi's Mac.

De keuze staat lokaal in ~/.config/mijnagents/whatsapp-wacht.json. Een ronde
leest geen WhatsApp-database, haalt geen media op en verstuurt geen berichten.
Alle foutteksten, hartslagen en dagtellingen zijn zonder bestandsnamen,
gesprekspartners en berichtinhoud.
"""

import argparse
from collections import defaultdict
import contextlib
from datetime import date, datetime, timezone
import fcntl
import io
import json
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile


CONFIG_PAD = Path.home() / ".config/mijnagents/whatsapp-wacht.json"
TOKEN_PAD = Path.home() / ".config/mijnagents/token"
STAAT_PAD = Path.home() / ".local/share/mijnagents/whatsapp-wacht/dagen.json"
LOCK_PAD = STAAT_PAD.parent / "ronde.lock"
EXPORT_MAP = Path.home() / ".local/share/mijnagents/whatsapp-wacht/exports"
MAX_EXPORT_BYTES = 50 * 1024 * 1024
MAX_CONFIG_BYTES = 64 * 1024
MAX_TOKEN_BYTES = 8 * 1024
MAX_REGEL = 1_000_000
MAX_GESPREKKEN = 20
VM = "globaal"
BORDSTAND = "~/agents/.venv/bin/python ~/appportal/mijnagents-runner/koppelingen/bordstand.py whatsapp-wacht --ronde"
STEMPEL = re.compile(
    r"^\[?(?P<datum>\d{1,2}[./-]\d{1,2}[./-]\d{2,4}),\s*"
    r"(?P<uur>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp]\.?[Mm]\.?)?)\]?"
    r"(?P<streep>\s+[-\u2013]\s+|\s+)(?P<rest>.*)$"
)
START_STEMPEL = re.compile(
    r"^\[?(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})"
    r"(?=,\s*\d{1,2}:\d{2}|\s+\d{1,2}:\d{2})"
)
UUR = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AaPp])\.?[Mm]\.?)?$")
KOP_MARKERS = "\ufeff\u200e\u200f\u202a\u202c"


class BronFout(RuntimeError):
    """Een veilige foutmelding zonder inhoud of naam van de privébron."""


def _prive_fd(pad, grens=MAX_EXPORT_BYTES, dir_fd=None):
    """Open zonder symlink en controleer precies de inode die gelezen wordt."""
    try:
        fd = os.open(pad, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
    except OSError:
        raise BronFout("Gekozen export of instellingen ontbreken") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise BronFout("Gekozen export of instellingen zijn niet privé opgeslagen")
        if info.st_size > grens:
            raise BronFout("Gekozen export of instellingen zijn te groot")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _beveiligd_regelmatig(pad, grens=MAX_EXPORT_BYTES):
    fd = _prive_fd(pad, grens)
    try:
        info = os.fstat(fd)
    finally:
        os.close(fd)
    return info


def _privemap(pad, soort="Exportmap"):
    try:
        fd = os.open(pad, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        raise BronFout(f"{soort} ontbreekt") from None
    try:
        info = os.fstat(fd)
    finally:
        os.close(fd)
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise BronFout(f"{soort} is niet privé opgeslagen")
    if any("dropbox" in deel.lower() for deel in pad.resolve().parts):
        raise BronFout(f"{soort} mag niet in Dropbox staan")
    return info


def _bestandsnaam(naam):
    return (isinstance(naam, str) and naam == Path(naam).name
            and naam not in ("", ".", "..") and not naam.startswith(".")
            and Path(naam).suffix.lower() in (".txt", ".zip")
            and not any(unicodedata.category(c) in ("Cc", "Cf") for c in naam))


def _unieke_json_sleutels(paren):
    """Laat geen last-wins selectie toe, ook niet in een genest gesprek."""
    data = {}
    for sleutel, waarde in paren:
        if sleutel in data:
            raise ValueError("Dubbele JSON-sleutel")
        data[sleutel] = waarde
    return data


def laad_config(pad=CONFIG_PAD):
    """Lees alleen de expliciete selectie. Elke onbekende of dubbele keuze stopt."""
    pad = Path(pad)
    _privemap(pad.parent, "Instellingenmap")
    try:
        with os.fdopen(_prive_fd(pad, MAX_CONFIG_BYTES), "r", encoding="utf-8") as bron:
            tekst = bron.read(MAX_CONFIG_BYTES + 1)
        if len(tekst) > MAX_CONFIG_BYTES:
            raise BronFout("Selectie-instellingen zijn te groot")
        data = json.loads(tekst, object_pairs_hook=_unieke_json_sleutels)
    except (OSError, UnicodeError, ValueError):
        raise BronFout("Selectie-instellingen zijn onleesbaar") from None
    if not isinstance(data, dict) or set(data) != {"versie", "export_map", "gesprekken"} or data["versie"] != 1:
        raise BronFout("Selectie-instellingen hebben een onbekende vorm")
    mapnaam = data["export_map"]
    if mapnaam != str(EXPORT_MAP):
        raise BronFout("Exportmap is niet de toegestane lokale map")
    export_map = Path(mapnaam)
    if export_map.resolve() != export_map:
        raise BronFout("Exportmap mag niet via een omleiding lopen")
    map_info = _privemap(export_map)
    chats = data["gesprekken"]
    if not isinstance(chats, list) or not 1 <= len(chats) <= MAX_GESPREKKEN:
        raise BronFout("Selectie moet minstens een gekozen gesprek bevatten")
    gekozen = set()
    afzenderparen = set()
    voor = []
    for chat in chats:
        if not isinstance(chat, dict) or set(chat) != {"bestand", "eigen_afzender", "andere_afzender", "datumvolgorde"}:
            raise BronFout("Gekozen gesprek heeft ongeldige instellingen")
        naam = chat["bestand"]
        if not _bestandsnaam(naam):
            raise BronFout("Gekozen export heeft een ongeldige bestandsnaam")
        sleutel = unicodedata.normalize("NFC", naam).casefold()
        if sleutel in gekozen:
            raise BronFout("Meerdere keuzes wijzen naar dezelfde export")
        gekozen.add(sleutel)
        ruwe_auteurs = (chat["eigen_afzender"], chat["andere_afzender"])
        if not all(isinstance(a, str) and a.strip() == a and a
                   and not any(unicodedata.category(c) in ("Cc", "Cf") for c in a) for a in ruwe_auteurs):
            raise BronFout("Afzenders van gekozen gesprek zijn ongeldig")
        auteurs = tuple(unicodedata.normalize("NFC", a) for a in ruwe_auteurs)
        if auteurs[0] == auteurs[1]:
            raise BronFout("Afzenders van gekozen gesprek zijn niet onderscheidbaar")
        if auteurs[0].startswith(auteurs[1] + ":") or auteurs[1].startswith(auteurs[0] + ":"):
            raise BronFout("Afzenders van gekozen gesprek zijn dubbelzinnig")
        paar = frozenset(auteurs)
        if paar in afzenderparen:
            raise BronFout("Meerdere keuzes hebben hetzelfde afzenderpaar")
        afzenderparen.add(paar)
        if chat["datumvolgorde"] not in ("DMY", "MDY"):
            raise BronFout("Datumvolgorde van gekozen gesprek is onbekend")
        bestand = export_map / naam
        _beveiligd_regelmatig(bestand)
        voor.append({"pad": bestand, "map_id": (map_info.st_dev, map_info.st_ino),
                     "eigen": auteurs[0], "andere": auteurs[1], "volgorde": chat["datumvolgorde"]})
    try:
        aanwezig = [unicodedata.normalize("NFC", p.name).casefold() for p in export_map.iterdir()
                    if p.name != ".DS_Store"]
    except OSError:
        raise BronFout("Exportmap is niet leesbaar") from None
    if len(aanwezig) != len(set(aanwezig)) or set(aanwezig) != gekozen:
        raise BronFout("Exportmap bevat ontbrekende of extra bestanden")
    return voor


def _regels(chat):
    """Lees een tekstexport of een ZIP met exact een _chat.txt, zonder uitpakken."""
    pad = chat["pad"]
    map_fd = None
    try:
        map_fd = os.open(pad.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        map_info = os.fstat(map_fd)
        if (map_info.st_dev, map_info.st_ino) != chat["map_id"]:
            raise BronFout("Gekozen exportmap is sinds de selectie gewijzigd")
        if map_info.st_mode & 0o077:
            raise BronFout("Exportmap is niet privé opgeslagen")
        with os.fdopen(_prive_fd(pad.name, dir_fd=map_fd), "rb") as bron:
            if pad.suffix.lower() == ".txt":
                yield from _decodeer(bron)
            else:
                with zipfile.ZipFile(bron) as pakket:
                    items = pakket.infolist()
                    if len(items) != 1 or items[0].filename != "_chat.txt" or items[0].file_size > MAX_EXPORT_BYTES:
                        raise BronFout("ZIP bevat niet uitsluitend een tekstgesprek zonder media")
                    if items[0].flag_bits & 1:
                        raise BronFout("Versleutelde ZIP wordt niet gelezen")
                    if items[0].compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                        raise BronFout("ZIP gebruikt een onbekende compressie")
                    with pakket.open(items[0], "r") as tekst:
                        yield from _decodeer(tekst)
    except BronFout:
        raise
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile):
        raise BronFout("Gekozen export is onleesbaar") from None
    finally:
        if map_fd is not None:
            os.close(map_fd)


def _decodeer(bron):
    with io.TextIOWrapper(bron, encoding="utf-8-sig", errors="strict") as tekst:
        try:
            totaal = 0
            while True:
                regel = tekst.readline(MAX_REGEL + 1)
                if not regel:
                    break
                if len(regel) > MAX_REGEL:
                    raise BronFout("Gekozen export heeft een te lange regel")
                totaal += len(regel.encode("utf-8"))
                if totaal > MAX_EXPORT_BYTES:
                    raise BronFout("Gekozen export is te groot")
                yield regel.rstrip("\r\n")
        except UnicodeError:
            raise BronFout("Gekozen export is geen UTF-8-tekst") from None


def _datum(tekst, volgorde):
    delen = re.split(r"[./-]", tekst)
    if len(delen) != 3:
        raise BronFout("Datum in gekozen export is onleesbaar")
    eerste, tweede, jaar = map(int, delen)
    if len(delen[2]) == 2:
        jaar += 2000
    dag, maand = (eerste, tweede) if volgorde == "DMY" else (tweede, eerste)
    try:
        uit = date(jaar, maand, dag)
    except ValueError:
        raise BronFout("Datum in gekozen export is ongeldig") from None
    if not 2000 <= uit.year <= datetime.now().year + 1:
        raise BronFout("Datum in gekozen export valt buiten het verwachte bereik")
    return uit.isoformat()


def _tijd(tekst):
    match = UUR.fullmatch(tekst)
    if not match:
        raise BronFout("Tijd in gekozen export is onleesbaar")
    uur, minuut, seconde = (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))
    if minuut > 59 or seconde > 59 or not (1 <= uur <= 12 if match.group(4) else 0 <= uur <= 23):
        raise BronFout("Tijd in gekozen export is ongeldig")


def tel_export(chat):
    """Tel berichtkoppen. Inhoud en afzendernamen verlaten deze functie niet."""
    dagen = defaultdict(lambda: {"inkomend": 0, "uitgaand": 0})
    berichten = 0
    for regel in _regels(chat):
        regel = regel.lstrip(KOP_MARKERS)
        if not START_STEMPEL.match(regel):
            continue  # vervolgregel van een bericht
        match = STEMPEL.match(regel)
        if not match:
            raise BronFout("Berichtkop in gekozen export is onleesbaar")
        _tijd(match.group("uur"))
        rest = unicodedata.normalize("NFC", "".join(
            c for c in match.group("rest") if unicodedata.category(c) != "Cf"))
        if rest.startswith(chat["eigen"] + ":"):
            if not rest[len(chat["eigen"]) + 1:].startswith((" ", "\t")):
                raise BronFout("Berichtkop in gekozen export is onleesbaar")
            richting = "uitgaand"
        elif rest.startswith(chat["andere"] + ":"):
            if not rest[len(chat["andere"]) + 1:].startswith((" ", "\t")):
                raise BronFout("Berichtkop in gekozen export is onleesbaar")
            richting = "inkomend"
        elif ":" in rest:
            raise BronFout("Gekozen export bevat een onverwachte afzender")
        else:
            continue  # systeemregel zonder afzender
        dag = _datum(match.group("datum"), chat["volgorde"])
        dagen[dag][richting] += 1
        berichten += 1
    if berichten == 0:
        raise BronFout("Gekozen export bevat geen herkenbare berichten")
    return dagen


def tel_geselecteerde(chats):
    dagen = defaultdict(lambda: {"inkomend": 0, "uitgaand": 0})
    for chat in chats:
        for dag, telling in tel_export(chat).items():
            dagen[dag]["inkomend"] += telling["inkomend"]
            dagen[dag]["uitgaand"] += telling["uitgaand"]
    return {dag: dagen[dag] for dag in sorted(dagen)}


def bewaar_dagen(pad, dagen):
    """Vervang het anonieme dagoverzicht atomisch; dezelfde invoer wijzigt niets."""
    pad = Path(pad)
    inhoud = json.dumps({"versie": 1, "dagen": dagen}, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    try:
        pad.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = pad.parent.lstat()
    except OSError:
        raise BronFout("Lokale staatmap is niet beschikbaar") from None
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or any(
            "dropbox" in deel.lower() for deel in pad.parent.resolve().parts):
        raise BronFout("Lokale staatmap is niet privé opgeslagen")
    if pad.exists() or pad.is_symlink():
        try:
            with os.fdopen(_prive_fd(pad), "r", encoding="utf-8") as bron:
                if bron.read() == inhoud:
                    return False
        except OSError:
            raise BronFout("Lokaal dagoverzicht is onleesbaar") from None
    tijdelijk = None
    try:
        fd, tijdelijk = tempfile.mkstemp(prefix=".dagen-", dir=pad.parent)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as bestand:
            bestand.write(inhoud)
            bestand.flush()
            os.fsync(bestand.fileno())
        os.replace(tijdelijk, pad)
        tijdelijk = None
        return True
    except OSError:
        raise BronFout("Lokaal dagoverzicht kon niet worden bewaard") from None
    finally:
        if tijdelijk is not None:
            try:
                os.unlink(tijdelijk)
            except OSError:
                pass


@contextlib.contextmanager
def exclusieve_ronde():
    """Houd één handmatige ronde van begin tot bevestiging op deze Mac actief."""
    map_info = _privemap(LOCK_PAD.parent, "Lokale staatmap")
    if map_info.st_mode & 0o777 != 0o700:
        raise BronFout("Lokale staatmap moet rechten 700 hebben")
    try:
        map_fd = os.open(LOCK_PAD.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        raise BronFout("Rondeslot is niet beschikbaar") from None
    try:
        info = os.fstat(map_fd)
        if ((info.st_dev, info.st_ino) != (map_info.st_dev, map_info.st_ino)
                or info.st_mode & 0o777 != 0o700):
            raise BronFout("Lokale staatmap is gewijzigd")
        try:
            fd = os.open(LOCK_PAD.name, os.O_CREAT | os.O_RDWR | os.O_NONBLOCK
                         | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=map_fd)
        except OSError:
            raise BronFout("Rondeslot is niet beschikbaar") from None
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o777 != 0o600:
                raise BronFout("Rondeslot is niet privé opgeslagen")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise BronFout("Er loopt al een WhatsApp-ronde") from None
            except OSError:
                raise BronFout("Rondeslot is niet beschikbaar") from None
            yield
        finally:
            os.close(fd)  # sluiten geeft de flock ook bij een fout vrij
    finally:
        os.close(map_fd)


@contextlib.contextmanager
def tunnel():
    """Gebruik het interne bord via een tijdelijke SSH-poort op alleen loopback."""
    proces = None
    try:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            poort = sock.getsockname()[1]
        proces = subprocess.Popen(
            ["/usr/bin/ssh", "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
             "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30",
             "-L", f"127.0.0.1:{poort}:127.0.0.1:3022", VM],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
            if proces.poll() is not None:
                raise BronFout("Bordtunnel is niet beschikbaar")
            with socket.socket() as sock:
                sock.settimeout(0.3)
                if sock.connect_ex(("127.0.0.1", poort)) == 0:
                    break
            time.sleep(0.3)
        else:
            raise BronFout("Bordtunnel is niet beschikbaar")
        yield f"http://127.0.0.1:{poort}"
    except OSError:
        raise BronFout("Bordtunnel is niet beschikbaar") from None
    finally:
        if proces is not None:
            if proces.poll() is None:
                proces.terminate()
            try:
                proces.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proces.kill()
                proces.wait()


def bord_stand():
    """Lees op de VM terug wat het bord echt opsloeg; toon geen SSH-uitvoer."""
    try:
        antwoord = subprocess.run(
            ["/usr/bin/ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20",
             VM, BORDSTAND],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=60, check=False,
        )
        if antwoord.returncode != 0:
            return None
        stand = json.loads(antwoord.stdout.decode("utf-8"))
        return stand if isinstance(stand, dict) else None
    except (OSError, subprocess.TimeoutExpired, UnicodeError, ValueError):
        return None


def bevestigd(stand, ronde_id):
    """Eindhartslag en kennis dragen allebei de eigen unieke ronde-ID."""
    if (not isinstance(stand, dict) or stand.get("status") not in ("klaar", "waakt")
            or stand.get("status_ronde") != ronde_id or stand.get("kennis_ronde") != ronde_id):
        return False
    def plausibel(waarde):
        try:
            tijdstip = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
            return 2000 <= tijdstip.year <= datetime.now(timezone.utc).year + 1
        except ValueError:
            return False

    return plausibel(stand.get("ts")) and plausibel(stand.get("kennis_ts"))


def run(config_pad=CONFIG_PAD, staat_pad=STAAT_PAD, token_pad=TOKEN_PAD):
    """Gedeelde ronde; geen externe schrijfactie behalve anonieme bordstatus."""
    try:
        with os.fdopen(_prive_fd(Path(token_pad), MAX_TOKEN_BYTES), "r", encoding="utf-8") as bron:
            token = bron.read(MAX_TOKEN_BYTES + 1).strip()
        if len(token) > MAX_TOKEN_BYTES:
            raise BronFout("Bordtoegang ontbreekt")
    except (BronFout, OSError, UnicodeError):
        raise BronFout("Bordtoegang ontbreekt") from None
    if not token:
        raise BronFout("Bordtoegang ontbreekt")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "koppelingen"))
    import bord  # noqa: E402
    bord.TOKEN = token  # lokaal bestand, nooit als argument of uitvoer
    ag = bord.Agent("whatsapp-wacht")
    ronde_id = secrets.token_hex(16)
    with exclusieve_ronde(), tunnel() as url:
        bord.PLATFORM = url
        with ag.ronde("gekozen WhatsApp-exports tellen") as ronde:
            try:
                nooit, beslist = bord.grenzen(ronde.werkwijze)
                if not nooit or not beslist:
                    raise BronFout("Bordwerkwijze mist veiligheidsgrenzen")
                ronde.bron(f"ronde-id-{ronde_id}", "")
                chats = laad_config(config_pad)
                dagen = tel_geselecteerde(chats)
                bewaar_dagen(staat_pad, dagen)
            except BronFout as fout:
                ronde.nood(str(fout), wie="mehdi")
                raise
            except Exception:
                # Het bord toont een onverwachte fout. Een OSError of parserfout
                # kan anders een privépad of een tekstfragment meeleveren.
                ronde.nood("Gekozen export kon niet veilig worden verwerkt", wie="mehdi")
                raise BronFout("Gekozen export kon niet veilig worden verwerkt") from None
            laatste = max(dagen)
            aantal = dagen[laatste]["inkomend"] + dagen[laatste]["uitgaand"]
            ronde.bron("gekozen-exportbeleid", f"{len(chats)} gekozen exports, anonieme dagtellingen")
            ronde.detail = (f"privé; {len(chats)} gekozen exports; laatste berichtdag {laatste}; "
                            f"op die dag {aantal} berichten; ronde-id:{ronde_id}")
        stand = bord_stand()
        if not bevestigd(stand, ronde_id):
            # Een overlappende, latere ronde kan intussen op het bord staan.
            # Overschrijf haar status niet met de fout van deze oude ronde.
            if isinstance(stand, dict) and stand.get("status_ronde") == ronde_id:
                ag.hartslag("fout", taak="gekozen WhatsApp-exports tellen",
                            detail="Bord heeft de ronde niet bevestigd")
            raise BronFout("Bord heeft de ronde niet bevestigd")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tel uitsluitend expliciet gekozen privé-WhatsApp-exports")
    parser.add_argument("--config", type=Path, default=CONFIG_PAD)
    parser.add_argument("--staat", type=Path, default=STAAT_PAD)
    args = parser.parse_args(argv)
    try:
        return 0 if run(args.config, args.staat) else 1
    except BronFout as fout:
        print(str(fout), file=sys.stderr)
        return 1
    except Exception:
        print("Bordronde kon niet veilig worden voltooid", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
