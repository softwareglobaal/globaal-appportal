"""Zoom, alleen lezen: de enige Zoom-koppeling van de agents (De Agendawacht, De Zoomwacht).

Twee profielen (ontwerp regie-zoom v1.2, Z1), elk met een eigen token en vervaltijd:
- stack: de Server-to-Server-app van de stack, ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID en ZOOM_CLIENT_SECRET in
  ~/appportal/.env, ~/appportal/mijnagents-data/.env of, zoals op 28-09-2026, ~/pipedrive-won-deals/.env. Die app delen
  won-deals, zoom-dossier, de aanvraagmelding en De Bode; De Agendawacht leest er de instellingen van een meeting mee
  (meeting:read:meeting:admin).
- lees: de alleen-lezende app "Zoomwacht lezen" van De Zoomwacht: ZOOM_LEES_CLIENT_ID en ZOOM_LEES_CLIENT_SECRET, met
  ZOOM_LEES_ACCOUNT_ID of anders ZOOM_ACCOUNT_ID, alleen uit ~/appportal/.env en ~/appportal/mijnagents-data/.env
  (zoom_leesapp.py --zet zet ze). Zonder die sleutels leest lees() met de app van de stack, en ook als ze er staan maar
  geen token geven (ZOO-10): dan onthoudt leesapp_fout() waarom, zodat De Zoomwacht een nood voor Mehdi zet. Een foute
  sleutel maakt de telling zo een ondergrens, geen onbekend en geen gebroken keten.
- nieuw: alleen voor zoom_leesapp.py --zet (RZ4-02, 22-10-2026). Het token van de net ingevoerde sleutels, alleen in het
  geheugen (nieuw_token), zodat de eigenaar van de nieuwe app gecontroleerd is voor er iets in .env komt. Dit profiel
  leest nooit een sleutel uit een bestand en valt nooit terug op de app van de stack: zonder token is het ZoomFout.

Nooit een sleutel in de code. Schrijven kan geen van beide apps: een instelling in Zoom veranderen blijft een
handeling van Mehdi. Een ontbrekend recht is een toestand (GeenRecht met de naam van het recht), geen crash en geen
stille 0. Een url komt nooit in een fouttekst; download- en afspeellinks bewaart alleen deze module, in het geheugen.

Grendels (13.2): lees() leest alleen onder het vaste gebruikers-id van Mehdi, /past_meetings/ en zijn eigen
meetingnummers (L5); download() alleen bestanden uit zijn eigen opnamelijst, en volgt een omleiding zelf, alleen naar
een host op zoom.us en zonder Authorization-kop na de eerste sprong (L1).
Grendels (13.6): een token van het profiel lees met een recht uit 'Nooit aanvinken' (rechten-zoomwacht-lezen.md) wordt
geweigerd, niet bewaard en nooit gebruikt (VerbodenRecht); lees() leest dan met de app van de stack en
leesapp_verboden() noemt het recht. Chatberichten (/chat/users/<id>/messages) nooit met de leesapp: die krijgt dat recht
bewust niet, het tellen van chatberichten blijft op de app van de stack (EIGEN-1).
Het Zoom-transcript (cloud_recording:read:meeting_transcript:admin) staat ook onder Nooit aanvinken en wordt sinds RZ3-04
(22-10-2026) geweigerd zoals de andere, tot Mehdi over dat recht beslist (TOT_MEHDI_BESLIST); tot dan gaf het alleen een
melding en las de leesapp ermee. Weigert Zoom een download, dan is dat GeenRecht bij download(), met het recht dat Zoom
noemt (of 'download' als het er geen noemt): zoom_leesapp.py meldt het bij de proefdownload, en noemt Mehdi alleen als
het het transcriptrecht is; De Zoomwacht zet een nood voor Mehdi.
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.zoom.us/v2"
_BESTANDEN = ("~/appportal/.env", "~/appportal/mijnagents-data/.env", "~/pipedrive-won-deals/.env")
_LEES_BESTANDEN = ("~/appportal/.env", "~/appportal/mijnagents-data/.env")
_tokens = {}
_meetings = {}
# L5: wat lees() mag lezen. Leeg tot de ronde het vaste gebruikers-id gezet heeft (vastzetten).
_VAST = {"id": "", "nummers": set()}
# Downloadlinks per bestandsid, alleen uit de eigen opnamelijst en alleen in het geheugen (Z4, L5).
_DOWNLOADS = {}
_MAX_SPRONGEN = 5
# ZOO-10: waarom de leesapp deze ronde geen token gaf (leeg: wel een token, of niet gevraagd), en welke verboden rechten
# haar token had (13.6). Een nieuwe ronde wist het.
_LEESAPP = {"fout": "", "verboden": []}
# RZ4-02: het profiel van net ingevoerde sleutels van de leesapp, alleen in het geheugen (nieuw_token)
NIEUW = "nieuw"
# 13.6 (rechten-zoomwacht-lezen.md, Nooit aanvinken): rechten die de leesapp nooit mag hebben. Elk recht dat schrijft,
# verandert of wist; een sleutel om als gebruiker een meeting te starten; de bediening van een ruimte; de inhoud van
# chatberichten, AI-samenvattingen en archieven. De app van de stack valt hier niet onder: die is gedeeld en kan meer.
VERBODEN_SOORTEN = frozenset({"write", "update", "delete"})
# Ook onder Nooit aanvinken, maar het vangnet kan het nodig hebben voor de Zoom-tekst. RZ3-04 (Codex RZ3-herstelcontrole,
# besluit van de regie 22-10-2026): geweigerd zoals de andere, tot Mehdi over dat recht beslist; de meldingen van
# zoom_leesapp.py zeggen dat. Tot dan aanvaardde de code het met alleen een melding (MELDEN_RECHTEN).
TOT_MEHDI_BESLIST = frozenset({"cloud_recording:read:meeting_transcript:admin"})
VERBODEN_RECHTEN = frozenset({"user:read:token:admin", "user:read:zak:admin", "zoom_rooms:read:virtual_controller:admin",
                              "meeting:read:local_archiving_token:admin", "team_chat:read:list_user_messages:admin",
                              "meeting:read:summary:admin", "aic:read:conversation_archives:admin"}) | TOT_MEHDI_BESLIST


class ZoomFout(RuntimeError):
    """Zoom gaf geen bruikbaar antwoord. De tekst draagt nooit een url of sleutel."""


class GeenRecht(ZoomFout):
    """De app mist een recht (Zoom 400 met code 4711, of 'does not contain scopes'). `scope` is de naam van het recht,
    of 'download' als een opname niet gedownload mag worden en Zoom geen recht noemde. `http` en `zoomcode` zijn de
    HTTP-code en de code van Zoom, als ze er zijn (RZ3-04: zoom_leesapp.py meldt zo welk recht ontbreekt, of dat Zoom
    er geen noemde)."""

    def __init__(self, scope, http=None, zoomcode=None):
        self.scope = scope or "onbekend recht"
        self.http, self.zoomcode = http, zoomcode
        super().__init__(f"geen recht: {self.scope}")


class Geweigerd(ZoomFout):
    """De grendel weigerde de vraag voor er iets naar Zoom ging (L1, L5)."""


class VerbodenRecht(Geweigerd):
    """Het token van de leesapp heeft een recht dat ze nooit mag hebben (13.6). `rechten` zijn de namen, nooit een waarde."""

    def __init__(self, rechten):
        self.rechten = list(rechten)
        super().__init__("verboden recht: " + ", ".join(self.rechten))


def verboden(rechten):
    """De rechten uit deze lijst die de leesapp nooit mag hebben, gesorteerd (13.6): elk recht met write, update of
    delete als deel van de naam, en de vaste lijst VERBODEN_RECHTEN."""
    return sorted(r for r in rechten if r.lower() in VERBODEN_RECHTEN or VERBODEN_SOORTEN & set(r.lower().split(":")))


def _sleutel(naam, bestanden=None):
    if os.environ.get(naam):
        return os.environ[naam].strip()
    for pad in _BESTANDEN if bestanden is None else bestanden:
        try:
            for regel in open(os.path.expanduser(pad)):
                if regel.startswith(naam + "="):
                    return regel.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return ""


def _lees_sleutel(naam):
    return _sleutel(naam, _LEES_BESTANDEN)


def beschikbaar(profiel="stack"):
    if profiel == "lees":
        return leesapp() or beschikbaar("stack")
    return all(_sleutel(n) for n in ("ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"))


def leesapp():
    """Staan de sleutels van de alleen-lezende app "Zoomwacht lezen"? Zonder die app is de telling een ondergrens."""
    return bool(_lees_sleutel("ZOOM_LEES_CLIENT_ID") and _lees_sleutel("ZOOM_LEES_CLIENT_SECRET")
                and (_lees_sleutel("ZOOM_LEES_ACCOUNT_ID") or _sleutel("ZOOM_ACCOUNT_ID")))


def ingang():
    """Met welke gebruiker de ronde begint: ZOOM_MEHDI_USER (zoom_leesapp.py zet die), anders 'me'. Elke vraag daarna
    gaat naar het id dat /users/<ingang> teruggeeft."""
    return _lees_sleutel("ZOOM_MEHDI_USER") or "me"


def leesapp_fout():
    """Waarom de leesapp deze ronde geen token gaf, of leeg. Dan las lees() met de app van de stack (ZOO-10)."""
    return _LEESAPP["fout"]


def leesapp_verboden():
    """De verboden rechten waarom het token van de leesapp deze ronde geweigerd werd (13.6), of een lege lijst."""
    return list(_LEESAPP["verboden"])


def _token_voor(profiel):
    """Het token voor een vraag. lees zonder sleutels leest met de app van de stack; geven de sleutels van de leesapp
    geen token, of een token met een verboden recht, dan ook, en leesapp_fout() zegt waarom. Een keer per ronde: daarna
    vraagt lees() geen token meer met sleutels die net faalden. Het profiel nieuw valt nooit terug (RZ4-02)."""
    if profiel == NIEUW:
        return _toegang(NIEUW)
    if profiel == "lees" and leesapp() and not _LEESAPP["fout"]:
        try:
            return _toegang("lees")
        except VerbodenRecht as e:
            _LEESAPP["fout"], _LEESAPP["verboden"] = "verboden recht", list(e.rechten)
        except ZoomFout as e:
            _LEESAPP["fout"] = str(e)[:80] or "geen token"
    return _toegang("stack")


def token_halen(cid, geheim, account):
    """Een token met deze waarden, alleen in het geheugen: het antwoord van Zoom (access_token, scope, expires_in), of
    ZoomFout zonder url of waarde. zoom_leesapp.py toetst er nieuwe sleutels mee voor er iets in .env komt (ZOO-10)."""
    basic = base64.b64encode(f"{cid}:{geheim}".encode()).decode()
    url = "https://zoom.us/oauth/token?" + urllib.parse.urlencode({"grant_type": "account_credentials", "account_id": account})
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, method="POST",
                                                                    headers={"Authorization": "Basic " + basic}), timeout=30))
    except urllib.error.HTTPError as e:
        raise ZoomFout(f"geen token (HTTP {e.code})") from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ZoomFout(f"geen token ({type(e).__name__})") from None
    if not isinstance(d, dict) or not d.get("access_token"):
        raise ZoomFout("geen token (antwoord zonder token)")
    return d


def nieuw_token(antwoord):
    """RZ4-02: het tokenantwoord van net ingevoerde sleutels (uit token_halen) als profiel nieuw, alleen in het geheugen.
    zoom_leesapp.py --zet controleert er met lees(..., profiel='nieuw') de eigenaar van de nieuwe app mee, voor er iets
    in .env komt. Een token met een verboden recht wordt niet bewaard (VerbodenRecht, 13.6). Geeft de rechten (alleen
    namen); nieuw_vergeten() wist het token weer."""
    if not isinstance(antwoord, dict) or not antwoord.get("access_token"):
        raise ZoomFout("geen token (antwoord zonder token)")
    namen = set((antwoord.get("scope") or "").split())
    if verboden(namen):
        raise VerbodenRecht(verboden(namen))
    _tokens[NIEUW] = {"waarde": antwoord["access_token"], "tot": time.time() + int(antwoord.get("expires_in", 3600)) - 120,
                      "rechten": namen}
    return set(namen)


def nieuw_vergeten():
    """RZ4-02: het token van de nieuwe sleutels uit het geheugen, na de controle, gelukt of niet."""
    _tokens.pop(NIEUW, None)


def _toegang(profiel="stack"):
    t = _tokens.get(profiel)
    if t and t["waarde"] and time.time() < t["tot"]:
        return t["waarde"]
    if profiel == NIEUW:
        # RZ4-02: alleen het token uit nieuw_token, nooit een sleutel uit een bestand en nooit de stack
        raise ZoomFout("geen token voor de nieuwe sleutels")
    if profiel == "lees":
        if not leesapp():
            raise ZoomFout("leesapp niet ingesteld")
        cid, geheim = _lees_sleutel("ZOOM_LEES_CLIENT_ID"), _lees_sleutel("ZOOM_LEES_CLIENT_SECRET")
        account = _lees_sleutel("ZOOM_LEES_ACCOUNT_ID") or _sleutel("ZOOM_ACCOUNT_ID")
    else:
        if not beschikbaar("stack"):
            raise ZoomFout("Zoom-sleutels van de stack ontbreken")
        cid, geheim, account = _sleutel("ZOOM_CLIENT_ID"), _sleutel("ZOOM_CLIENT_SECRET"), _sleutel("ZOOM_ACCOUNT_ID")
    d = token_halen(cid, geheim, account)
    namen = set((d.get("scope") or "").split())
    if profiel == "lees" and verboden(namen):
        # 13.6: de leesapp mag niets schrijven en geen inhoud lezen. Het token wordt niet bewaard en nooit gebruikt.
        raise VerbodenRecht(verboden(namen))
    _tokens[profiel] = {"waarde": d["access_token"], "tot": time.time() + int(d.get("expires_in", 3600)) - 120,
                        "rechten": namen}
    return _tokens[profiel]["waarde"]


def rechten(profiel="lees"):
    """De rechten van de app, uit het veld scope van het tokenantwoord (alleen namen). Heeft de leesapp een verboden
    recht, dan VerbodenRecht met de namen (13.6)."""
    _toegang(profiel)
    return set(_tokens[profiel]["rechten"])


# ------------------------------------------------------------------ http ---
class _GeenOmleiding(urllib.request.HTTPRedirectHandler):
    """L1: urllib stuurt bij een omleiding alle koppen mee, ook naar een andere host. Elke sprong beoordelen we zelf."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_GeenOmleiding)


def _vraag(url, koppen, max_bytes=2_000_000):
    """Eén GET zonder automatische omleiding: (HTTP-code, Location, inhoud). Een netwerkfout wordt ZoomFout, zonder url."""
    req = urllib.request.Request(url, headers=koppen)
    try:
        with _OPENER.open(req, timeout=60) as r:
            return r.status, "", r.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        try:
            inhoud = e.read(4096) or b""
        except OSError:
            inhoud = b""
        return e.code, (e.headers.get("Location", "") if e.headers else ""), inhoud
    except (urllib.error.URLError, OSError) as e:
        raise ZoomFout(f"Zoom niet bereikbaar ({type(e).__name__})") from None


def _scope_uit(tekst):
    """De naam van het ontbrekende recht uit de melding van Zoom ('... does not contain scopes:[a, b:admin]'); een
    recht met :admin gaat voor, want de Server-to-Server-app krijgt de admin-rechten."""
    m = re.search(r"scopes?\s*:?\s*\[([^\]]+)\]", tekst or "")
    if not m:
        return ""
    namen = [s.strip() for s in m.group(1).split(",") if s.strip()]
    return next((s for s in namen if s.endswith(":admin")), namen[0] if namen else "")


def _zoom_host(url):
    d = urllib.parse.urlsplit(url)
    host = (d.hostname or "").lower()
    return d.scheme == "https" and (host == "zoom.us" or host.endswith(".zoom.us"))


# ----------------------------------------------------------- de grendel ---
def vastzetten(gebruiker_id, nummers=()):
    """L5: vanaf hier leest lees() alleen nog wat bij dit gebruikers-id hoort, plus /past_meetings/ en de meetings met
    deze nummers. Met None begint een nieuwe ronde: alleen /users/<ingang> en /users/me mogen, de downloadtabel is leeg,
    en de leesapp krijgt opnieuw een kans op een token (ZOO-10)."""
    _VAST["id"] = gebruiker_id or ""
    _VAST["nummers"] = {str(n) for n in nummers if n}
    if not gebruiker_id:
        _DOWNLOADS.clear()
        _LEESAPP["fout"], _LEESAPP["verboden"] = "", []


def nummer_erbij(nummer):
    """Een eigen meetingnummer dat /meetings/<nummer> mag lezen (bv. uit Mehdi's eigen rijen in de gesprekkentabel)."""
    if nummer:
        _VAST["nummers"].add(str(nummer))


def toegestaan(pad):
    p = pad.split("?", 1)[0]
    if "#" in p or ".." in p.split("/") or "%2e" in p.lower():
        return False
    m = re.fullmatch(r"/meetings/(\d+)", p)
    if m:
        return m.group(1) in _VAST["nummers"]
    vast = _VAST["id"]
    if not vast:
        # /users/me is de eigenaar van de app zelf: zoom_leesapp.py toetst er de gebruiker mee, ook als ZOOM_MEHDI_USER
        # al staat (ZOO-08). Het geeft een gebruiker, niet zijn meetings; die mogen pas onder het vaste id.
        return p in (f"/users/{ingang()}", "/users/me")
    if p == f"/users/{vast}" or p.startswith(f"/users/{vast}/"):
        return True
    if p.startswith(f"/report/users/{vast}/") or p.startswith(f"/chat/users/{vast}/"):
        return True
    return p.startswith("/past_meetings/") and len(p) > len("/past_meetings/")


# ---------------------------------------------------------------- lezen ---
def lees(pad, params=None, profiel="lees"):
    """Een GET op de Zoom-API. 200 geeft het antwoord, 404 None. Een ontbrekend recht geeft GeenRecht(scope), elke
    andere fout ZoomFout, zonder url. Een pad buiten het vaste gebruikers-id geeft Geweigerd, zonder vraag aan Zoom; zo
    ook chatberichten met de leesapp (EIGEN-1)."""
    if not toegestaan(pad):
        raise Geweigerd("pad buiten de vaste gebruiker van Mehdi geweigerd")
    if profiel != "stack" and re.fullmatch(r"/chat/users/[^/]+/messages", pad.split("?", 1)[0]):
        raise Geweigerd("chatberichten alleen met de app van de stack")
    url = API + pad + ("?" + urllib.parse.urlencode(params) if params else "")
    code, _, inhoud = _vraag(url, {"Authorization": "Bearer " + _token_voor(profiel)})
    if code == 200:
        try:
            return json.loads((inhoud or b"").decode("utf-8") or "{}")
        except ValueError:
            raise ZoomFout("onleesbaar antwoord van Zoom") from None
    if code == 404:
        return None
    tekst = (inhoud or b"").decode("utf-8", "replace")
    try:
        zoomcode = json.loads(tekst).get("code")
    except (ValueError, AttributeError):
        zoomcode = None
    if code in (400, 401, 403) and (zoomcode == 4711 or "does not contain scope" in tekst):
        raise GeenRecht(_scope_uit(tekst))
    raise ZoomFout(f"HTTP {code}" + (f" (Zoom-code {zoomcode})" if isinstance(zoomcode, int) else ""))


def lees_alles(pad, params, sleutel, profiel="lees"):
    """Alle pagina's (next_page_token) van een lijst. None als Zoom de lijst niet kent (404): onbekend is niet leeg."""
    uit, p = [], dict(params or {})
    while True:
        d = lees(pad, p, profiel)
        if d is None:
            if p.get("next_page_token"):
                raise ZoomFout("volgende pagina niet gevonden")
            return None
        uit += d.get(sleutel) or []
        if not d.get("next_page_token"):
            return uit
        p["next_page_token"] = d["next_page_token"]


def uuid_pad(uuid):
    """Zoom eist dubbele codering als een uuid met / begint of // bevat."""
    q = urllib.parse.quote(uuid, safe="")
    return urllib.parse.quote(q, safe="") if uuid.startswith("/") or "//" in uuid else q


def opnames(van_dag, tot_dag, profiel="lees"):
    """De cloudopnames van de vaste gebruiker tussen twee datums (JJJJ-MM-DD), zonder een enkele link: per meeting
    uuid, nummer, onderwerp, start, duur en de bestanden (id, soort, status, start, einde). De downloadlink gaat alleen
    in de tabel van deze module, per bestandsid; afspeel- en deellinks en toegangscodes worden meteen weggegooid."""
    if not _VAST["id"]:
        raise Geweigerd("opnames: eerst de vaste gebruiker zetten")
    lijst = lees_alles(f"/users/{_VAST['id']}/recordings", {"from": van_dag, "to": tot_dag, "page_size": 300}, "meetings", profiel)
    if lijst is None:
        raise ZoomFout("opnamelijst niet gevonden")
    uit = []
    for m in lijst:
        bestanden = []
        for f in m.get("recording_files") or []:
            bid = str(f.get("id") or "")
            if bid and f.get("download_url"):
                _DOWNLOADS[bid] = f["download_url"]
            bestanden.append({"id": bid, "soort": f.get("file_type") or "", "status": f.get("status") or "",
                              "start": f.get("recording_start") or "", "einde": f.get("recording_end") or ""})
        uit.append({"uuid": m.get("uuid") or "", "nummer": str(m.get("id") or ""), "onderwerp": m.get("topic") or "",
                    "start": m.get("start_time") or "", "duur": int(m.get("duration") or 0), "bestanden": bestanden})
    return uit


def download(bestandsid, profiel="lees", max_bytes=5_000_000):
    """Een opnamebestand in het geheugen, alleen als het in de eigen opnamelijst stond (L5). Een omleiding volgen we
    zelf: alleen naar https op zoom.us, en na de eerste sprong zonder Authorization-kop (L1). 401, 403, of 400 met code
    4711 is GeenRecht: met het recht dat Zoom in zijn melding noemt, anders 'download', en met de HTTP-code en de code
    van Zoom. Tot 22-10-2026 gooide ik de naam van het recht weg (tegenproef op RZ3-04)."""
    url = _DOWNLOADS.get(str(bestandsid))
    if not url:
        raise Geweigerd("download: bestand staat niet in de eigen opnamelijst")
    koppen = {"Authorization": "Bearer " + _token_voor(profiel)}
    for sprong in range(_MAX_SPRONGEN):
        if not _zoom_host(url):
            raise Geweigerd("download: omleiding naar een host buiten zoom.us geweigerd")
        code, waarheen, inhoud = _vraag(url, koppen if sprong == 0 else {}, max_bytes)
        if code in (301, 302, 303, 307, 308):
            if not waarheen:
                raise ZoomFout(f"download: omleiding zonder doel (HTTP {code})")
            url = urllib.parse.urljoin(url, waarheen)
            continue
        tekst = (inhoud or b"")[:4096].decode("utf-8", "replace") if code != 200 else ""
        if code in (401, 403) or (code == 400 and ("4711" in tekst or "does not contain scope" in tekst)):
            try:
                zoomcode = json.loads(tekst).get("code")
            except (ValueError, AttributeError):
                zoomcode = None
            raise GeenRecht(_scope_uit(tekst) or "download", http=code, zoomcode=zoomcode if isinstance(zoomcode, int) else None)
        if code != 200:
            raise ZoomFout(f"download: HTTP {code}")
        if len(inhoud) > max_bytes:
            raise ZoomFout("download: groter dan toegelaten")
        return inhoud
    raise ZoomFout("download: te veel omleidingen")


def meeting(mid):
    """De meeting met haar instellingen, of None als ze niet te lezen is. Een keer per ronde (De Agendawacht)."""
    if mid in _meetings:
        return _meetings[mid]
    try:
        req = urllib.request.Request(f"{API}/meetings/{mid}",
                                     headers={"Authorization": "Bearer " + _toegang("stack")})
        _meetings[mid] = json.load(urllib.request.urlopen(req, timeout=30))
    except (urllib.error.URLError, KeyError, ValueError, OSError, ZoomFout):
        _meetings[mid] = None
    return _meetings[mid]
