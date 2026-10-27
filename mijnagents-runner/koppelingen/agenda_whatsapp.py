"""WhatsApp-meldingen van de Agendawacht aan Mehdi (Mehdi, 27-10-2026; driehoeksoverleg W1 tot W10).

Mehdi: "wanneer de Agendawacht een afspraak uit mail in de agenda zet, stuurt hij Mehdi een korte WhatsApp-melding met:
wat, wanneer, welke agenda, en een eventuele botsing met een bestaande afspraak. Bij een botsing zet hij de afspraak als
'te valideren' en wacht op Mehdi's antwoord via WhatsApp." Mehdi werkt alleen via WhatsApp.

- De Agendawacht zet een melding klaar (klaarzetten); alleen De Bode verstuurt (versturen), alleen via WhatsApp, nooit
  in de stille uren en nooit via Telegram (de regel van 25-09-2026 over Telegram blijft).
- De wachtrij staat alleen hier, in mijnagents-data: niet op het bord en niet in de export, want de tekst noemt een
  zorgafspraak (bode.md, agenda-wacht.md: medisch is privé).
- Elke melding heeft een verzendspoor: klaar -> bezig -> verzonden. Blijft een melding 'bezig' (de ronde werd
  onderbroken tijdens het versturen), dan stuur ik ze niet blind opnieuw: ze wordt 'onzeker' en een nood (Codex, W1).
- Een vraag heeft een code (A1, A2, ...). Alleen een antwoord met die code telt: 'A3 ja' of 'A3 vervalt'. Een los 'ja'
  gaat gewoon naar De Regisseur, zodat het nooit de verkeerde afspraak goedkeurt (Codex, W5).
"""
import fcntl
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

BRUSSEL = ZoneInfo("Europe/Brussels")
WACHTRIJ = os.path.expanduser("~/appportal/mijnagents-data/agenda-whatsapp.json")
KOP = "Agendawacht"
MAX_POGINGEN = 3            # zo vaak weigert Meta een melding voor ze 'mislukt' is
ANTWOORD = re.compile(r"^\s*(?:@?agendawacht\s*[,:]?\s*)?(?:(?P<c1>a\s?\d{1,4})\s*[:,.\-]?\s*(?P<k1>ja|vervalt)"
                      r"|(?P<k2>ja|vervalt)\s*[:,.\-]?\s*(?P<c2>a\s?\d{1,4}))\s*[.!]*\s*$", re.I)
CODE_ALLEEN = re.compile(r"^\s*(?:@?agendawacht\s*[,:]?\s*)?(?P<c>a\s?\d{1,4})\b", re.I)


def _nu():
    return datetime.now(BRUSSEL)


def _leeg():
    return {"volgende": 1, "meldingen": {}}


def _lees():
    try:
        with open(WACHTRIJ, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("meldingen"), dict):
            return d
    except FileNotFoundError:
        return _leeg()
    except (OSError, ValueError):
        pass
    raise OSError("de wachtrij van de agendameldingen is niet te lezen")   # nooit stil opnieuw beginnen: dan dubbel


@contextmanager
def _bewerk():
    """De wachtrij lezen en schrijven onder een slot: De Bode, de Agendawacht en het agendasignaal schrijven erin."""
    os.makedirs(os.path.dirname(WACHTRIJ), exist_ok=True)
    with open(WACHTRIJ + ".lock", "w", encoding="utf-8") as slot:
        fcntl.flock(slot, fcntl.LOCK_EX)
        d = _lees()
        yield d
        tmp = f"{WACHTRIJ}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=0)
        os.replace(tmp, WACHTRIJ)


def bekend(sleutel):
    """Staat deze versie al in de wachtrij (verstuurd, te versturen of als basislijn)?"""
    return sleutel in _lees()["meldingen"]


def basislijn_gezet():
    return bool(_lees().get("basislijn"))


def basislijn(sleutels):
    """Eerste ronde (W8): de bestaande versies zonder botsing worden bekend, zonder melding."""
    with _bewerk() as d:
        for k in sleutels:
            d["meldingen"].setdefault(k, {"status": "basis", "gemaakt": _nu().isoformat()})
        d["basislijn"] = _nu().isoformat()


def klaarzetten(sleutel, tekst, vraag=None):
    """Zet een melding klaar voor De Bode, eenmaal per sleutel (afspraak en versie). '{code}' in de tekst wordt de code
    van de melding. vraag: {'id': ...} van de afspraak die op antwoord wacht. Geeft de code."""
    with _bewerk() as d:
        if sleutel in d["meldingen"] and d["meldingen"][sleutel].get("status") != "basis":
            return d["meldingen"][sleutel].get("code")
        code = f"A{int(d.get('volgende') or 1)}"
        d["volgende"] = int(d.get("volgende") or 1) + 1
        d["meldingen"][sleutel] = {"code": code, "tekst": tekst.replace("{code}", code), "status": "klaar",
                                   "gemaakt": _nu().isoformat(), "vraag": vraag, "antwoord": None, "verwerkt": None,
                                   "pogingen": 0}
        return code


def versturen(stuur_wa, nood, stil, niet_beschikbaar=()):
    """Door De Bode, elke ronde: de klaarstaande meldingen naar Mehdi, alleen via WhatsApp (stuur_wa(tekst, kop=...)).
    In de stille uren niets. niet_beschikbaar: de uitzondering(en) voor 'nu niet' (dagplafond, venster): dan blijft
    de melding klaar staan. Geeft het aantal verzonden meldingen."""
    if stil:
        return 0
    with _bewerk() as d:
        for k, m in d["meldingen"].items():
            if m.get("status") == "bezig":       # vorige ronde onderbroken tijdens het versturen: niet gokken
                m["status"] = "onzeker"
                nood.append({"tekst": f"Agendawacht: melding {m.get('code')} misschien al verstuurd en onderbroken; "
                                      "niet herhaald, kijk ze na", "wie": "claude-code"})
        te_sturen = [k for k, m in d["meldingen"].items() if m.get("status") == "klaar"]
        for k in te_sturen:
            d["meldingen"][k]["status"] = "bezig"
            d["meldingen"][k]["poging"] = _nu().isoformat()
        teksten = {k: d["meldingen"][k]["tekst"] for k in te_sturen}
    n = 0
    for k in te_sturen:
        try:
            kanaal = stuur_wa(teksten[k], kop=KOP)
            nieuw, extra = "verzonden", {"kanaal": kanaal, "verzonden": _nu().isoformat()}
            n += 1
        except tuple(niet_beschikbaar) as e:        # zeker niet vertrokken: later opnieuw
            nieuw, extra = "klaar", {"wacht": str(e)[:160]}
            nood.append({"tekst": "Agendawacht: een WhatsApp-melding wacht op het venster of het dagplafond", "wie": "mehdi"})
        except RuntimeError as e:                   # Meta weigerde het bericht: zeker niet vertrokken
            nieuw, extra = "klaar", {"fout": str(e)[:160]}
        except Exception as e:  # noqa: BLE001      # bv. een time-out: misschien vertrokken
            nieuw, extra = "onzeker", {"fout": f"{type(e).__name__}"}
            nood.append({"tekst": f"Agendawacht: WhatsApp-melding misschien niet aangekomen ({type(e).__name__}); "
                                  "niet herhaald", "wie": "claude-code"})
        with _bewerk() as d:
            m = d["meldingen"].get(k)
            if m is None:
                continue
            if nieuw == "klaar" and "fout" in extra:
                m["pogingen"] = int(m.get("pogingen") or 0) + 1
                if m["pogingen"] >= MAX_POGINGEN:
                    nieuw = "mislukt"
                    nood.append({"tekst": f"Agendawacht: WhatsApp-melding {m.get('code')} door Meta geweigerd", "wie": "claude-code"})
            m["status"] = nieuw
            m.update(extra)
    return n


def antwoord_herkennen(tekst):
    """Is dit WhatsApp-bericht van Mehdi een antwoord op een open agendavraag? 'A3 ja', 'A3 vervalt', 'ja A3'. Geeft
    None (geen agendabericht: gewoon naar het bord), of de zin waarmee ik het ontvangen bevestig. Een bericht dat met een
    code begint maar niet past, krijgt uitleg; het telt niet als antwoord."""
    t = (tekst or "").strip()
    m = ANTWOORD.match(t)
    c = CODE_ALLEEN.match(t)
    if not m and not c:
        return None
    code = "A" + re.sub(r"\D", "", (m.group("c1") or m.group("c2")) if m else c.group("c"))
    with _bewerk() as d:
        vraag = next((v for v in d["meldingen"].values() if v.get("code") == code and v.get("vraag")), None)
        if vraag is None:
            if not m:
                return None                         # 'A4 is een papierformaat': geen agendacode, gewoon naar het bord
            uit = f"Agendawacht: ik ken geen vraag {code}. Antwoord met de code uit mijn bericht."
        elif not m:
            uit = f"Agendawacht: antwoord met '{code} ja' (beide laten staan) of '{code} vervalt'."
        elif vraag.get("antwoord"):
            uit = f"Agendawacht: {code} is al beantwoord ({vraag['antwoord']})."
        else:
            keuze = (m.group("k1") or m.group("k2")).lower()
            vraag["antwoord"], vraag["antwoord_tijd"] = keuze, _nu().isoformat()
            uit = f"Agendawacht: {code} {keuze} ontvangen. Ik zet het in je agenda en bevestig binnen een kwartier."
    klaarzetten(f"ontvangst:{code}:{_nu():%Y%m%d%H%M%S%f}", uit)
    return uit


def open_antwoorden():
    """[(sleutel, melding)] met een antwoord dat de Agendawacht nog moet verwerken."""
    return [(k, m) for k, m in _lees()["meldingen"].items() if m.get("vraag") and m.get("antwoord") and not m.get("verwerkt")]


def verwerkt(sleutel, uitkomst):
    with _bewerk() as d:
        if sleutel in d["meldingen"]:
            d["meldingen"][sleutel]["verwerkt"] = {"tijd": _nu().isoformat(), "uitkomst": uitkomst}
