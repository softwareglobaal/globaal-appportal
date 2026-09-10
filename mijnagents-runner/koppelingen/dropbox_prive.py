"""Mehdi's eigen Dropbox (privé-archief), los van het team-token van de stack.

Sleutels bij naam uit ~/appportal/.env: DROPBOX_PRIVE_APP_KEY, DROPBOX_PRIVE_APP_SECRET,
DROPBOX_PRIVE_REFRESH_TOKEN (koppelen: dropbox_prive_koppelen.py). Optioneel
DROPBOX_PRIVE_BASIS: de map waaronder alles landt; leeg bij een app met
"App folder"-toegang (dan is de app-map zelf de wortel), bijvoorbeeld
"/Mehdi Agents" bij volledige toegang.

Eén taak: een lokale map (archief op de VM) spiegelen naar Dropbox. Alleen
schrijven, nooit verwijderen; wat lokaal weg is, blijft in Dropbox staan. Welke
bestanden al geüpload zijn staat in <lokale map>/.dropbox_gespiegeld.json
(pad -> grootte + mtime), zodat een ronde alleen het nieuwe verstuurt."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.dropboxapi.com"
INHOUD = "https://content.dropboxapi.com"
STAAT = ".dropbox_gespiegeld.json"
MAX_BESTAND = 140 * 1024 * 1024  # enkele upload-call; groter slaan we over met melding


def _env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_env("~/appportal/.env")
_token = {"waarde": "", "tot": 0.0}


def beschikbaar():
    return all(os.environ.get(n, "").strip() for n in
               ("DROPBOX_PRIVE_APP_KEY", "DROPBOX_PRIVE_APP_SECRET", "DROPBOX_PRIVE_REFRESH_TOKEN"))


def basis():
    b = os.environ.get("DROPBOX_PRIVE_BASIS", "").strip().rstrip("/")
    return ("/" + b.lstrip("/")) if b else ""


def _toegang():
    if _token["waarde"] and time.time() < _token["tot"]:
        return _token["waarde"]
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": os.environ["DROPBOX_PRIVE_REFRESH_TOKEN"].strip(),
        "client_id": os.environ["DROPBOX_PRIVE_APP_KEY"].strip(),
        "client_secret": os.environ["DROPBOX_PRIVE_APP_SECRET"].strip(),
    }).encode()
    with urllib.request.urlopen(f"{API}/oauth2/token", data, timeout=20) as r:
        a = json.load(r)
    _token["waarde"], _token["tot"] = a["access_token"], time.time() + int(a.get("expires_in", 14400)) - 300
    return _token["waarde"]


def _verzoek(url, data, koppen, pogingen=5):
    """POST met herkansing bij 429 (Retry-After) en 5xx."""
    wacht = 5
    for poging in range(pogingen):
        req = urllib.request.Request(url, data, {"Authorization": f"Bearer {_toegang()}", **koppen})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                if poging == pogingen - 1:
                    raise
                try:
                    pauze = max(int(e.headers.get("Retry-After", "0")), wacht)
                except ValueError:
                    pauze = wacht
                time.sleep(min(pauze, 120))
                wacht *= 2
                continue
            raise


def rpc(pad, body):
    return _verzoek(f"{API}/2/{pad}", json.dumps(body).encode(), {"Content-Type": "application/json"})


def account():
    """E-mail en naam van het gekoppelde account (om te zien dat het Mehdi's is)."""
    a = _verzoek(f"{API}/2/users/get_current_account", b"null", {"Content-Type": "application/json"})
    return {"email": a.get("email", ""), "naam": (a.get("name") or {}).get("display_name", ""),
            "type": (a.get("account_type") or {}).get(".tag", "")}


def upload(inhoud, extern_pad, overschrijf=True):
    """Eén bestand naar Dropbox; extern_pad is absoluut binnen de wortel (basis komt ervoor)."""
    arg = {"path": basis() + extern_pad, "mode": "overwrite" if overschrijf else "add", "mute": True, "autorename": False}
    return _verzoek(f"{INHOUD}/2/files/upload", inhoud,
                    {"Content-Type": "application/octet-stream", "Dropbox-API-Arg": json.dumps(arg)})


def _laad_staat(lokaal):
    try:
        return json.load(open(os.path.join(lokaal, STAAT), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def spiegel_map(lokaal, extern, max_per_ronde=400):
    """Alle nieuwe of gewijzigde bestanden onder `lokaal` naar Dropbox-map `extern`.
    Geeft {"verstuurd": n, "overgeslagen": n, "rest": n, "fout": tekst of ""}."""
    uit = {"verstuurd": 0, "overgeslagen": 0, "rest": 0, "fout": ""}
    if not beschikbaar() or not os.path.isdir(lokaal):
        return uit
    staat = _laad_staat(lokaal)
    te_doen = []
    for wortel, _mappen, bestanden in os.walk(lokaal):
        for b in sorted(bestanden):
            if b == STAAT or b.startswith("."):
                continue
            vol = os.path.join(wortel, b)
            rel = os.path.relpath(vol, lokaal).replace(os.sep, "/")
            st = os.stat(vol)
            kenmerk = [st.st_size, int(st.st_mtime)]
            if staat.get(rel) == kenmerk:
                continue
            if st.st_size > MAX_BESTAND:
                uit["overgeslagen"] += 1
                continue
            te_doen.append((vol, rel, kenmerk))
    for vol, rel, kenmerk in te_doen[:max_per_ronde]:
        try:
            upload(open(vol, "rb").read(), f"{extern.rstrip('/')}/{rel}")
            staat[rel] = kenmerk
            uit["verstuurd"] += 1
        except Exception as e:  # noqa: BLE001
            uit["fout"] = f"{rel}: {type(e).__name__} {str(e)[:120]}"
            break
    uit["rest"] = len(te_doen) - uit["verstuurd"]
    try:
        json.dump(staat, open(os.path.join(lokaal, STAAT), "w", encoding="utf-8"))
    except OSError:
        pass
    return uit


def nood(wie="mehdi", wat="het archief"):
    """De standaardnood als het token ontbreekt, voor de hartslag van een wacht."""
    return [] if beschikbaar() else [{"tekst": f"Geen privé-Dropbox-token: {wat} staat op de VM, niet in Mehdi's eigen Dropbox "
                                                "(koppelen: dropbox_prive_koppelen.py)", "wie": wie}]
