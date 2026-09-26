"""De stem van De Bode: Mehdi kan terugpraten als een agent hem belt (26-09-2026).

roep_mehdi (mijnagents/mcp_bode.py) zet een rij in de tabel stemgesprek en laat Twilio bellen met
<Connect><Stream url="wss://mijnagents.<domein>/stem/ws">. Twilio stuurt het geluid van het gesprek
(G.711 mu-law, 8 kHz, base64) naar deze server; wij geven het ongewijzigd door aan de OpenAI Realtime
API en sturen de stem terug naar Twilio. Er wordt niets omgezet: beide kanten spreken pcmu.

De stem begint met de zin van de agent, vraagt wat Mehdi wil, legt zijn antwoord vast met de functie
noteer_antwoord en hangt op. Het antwoord komt in de rij (roep_mehdi's oproep_status geeft het terug
aan Claude), op Telegram en in het logboek van De Bode.

Grenzen: een gesprek duurt hooguit MAX_SECONDEN; gevoelige gegevens (paspoort, rekening, wachtwoord,
codes) worden nooit genoteerd; wie de stroom opent moet een geldig teken (HMAC) meegeven.
Omgeving (mijnagents-data/.env): OPENAI_API_KEY, MIJNAGENTS_MCP_SECRET (voor het teken), en optioneel
OPENAI_REALTIME_MODEL (standaard gpt-realtime-2.1), OPENAI_REALTIME_STEM (standaard marin).
"""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone

from aiohttp import WSMsgType, web, ClientSession

DB = os.environ.get("AGENTS_DB", "/data/mijnagents.db")
MODEL = os.environ.get("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1-mini")
# USD per 1 miljoen tokens (developers.openai.com/api/docs/pricing, gelezen 26-09-2026):
# tekst in, tekst in cached, tekst uit, audio in, audio in cached, audio uit.
PRIJZEN = {"gpt-realtime-2.1": (4.00, 0.40, 24.00, 32.00, 0.40, 64.00),
           "gpt-realtime-2.1-mini": (0.60, 0.06, 2.40, 10.00, 0.30, 20.00)}
TWILIO_PRIJS_WACHT = (120, 300)   # seconden na het gesprek: Twilio zet de prijs pas na een tijdje
OPHANG_WACHT = float(os.environ.get("STEM_OPHANG_WACHT", "6"))  # s: zegt het model na 'ophangen' niets meer, dan toch ophangen
EERSTE_WACHT = float(os.environ.get("STEM_EERSTE_WACHT", "3.5"))  # s: zegt Mehdi bij het opnemen niets, dan begint De Bode zelf
ACHTERGROND = set()               # lopende achtergrondtaken (prijs ophalen, ophang-wachter)


def sleutel():
    """OPENAI_API_KEY uit de omgeving, anders uit ~/agents/.env (alleen-lezen gemount op /run/agents.env).
    Alleen die ene regel wordt gelezen; de rest van dat bestand blijft onaangeroerd."""
    k = os.environ.get("OPENAI_API_KEY", "").strip()
    if k:
        return k
    try:
        for r in open("/run/agents.env", encoding="utf-8"):
            if r.startswith("OPENAI_API_KEY="):
                return r.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def kosten_usd(model, u):
    """Kosten van een gesprek uit de opgetelde usage van alle response.done-events."""
    ti, tc, to, ai, ac, ao = PRIJZEN.get(model, PRIJZEN["gpt-realtime-2.1"])
    i, o = u.get("input_token_details") or {}, u.get("output_token_details") or {}
    cd = i.get("cached_tokens_details") or {}
    c_t, c_a = cd.get("text_tokens", 0), cd.get("audio_tokens", 0)
    som = ((i.get("text_tokens", 0) - c_t) * ti + c_t * tc + (i.get("audio_tokens", 0) - c_a) * ai + c_a * ac
           + o.get("text_tokens", 0) * to + o.get("audio_tokens", 0) * ao)
    return round(som / 1_000_000, 5)


def tel_op(totaal, u):
    """Telt een usage-dict (geneste getallen) op bij het totaal."""
    for k, v in (u or {}).items():
        if isinstance(v, dict):
            tel_op(totaal.setdefault(k, {}), v)
        elif isinstance(v, (int, float)):
            totaal[k] = totaal.get(k, 0) + v
STEM = os.environ.get("OPENAI_REALTIME_STEM", "marin")
MAX_SECONDEN = int(os.environ.get("STEM_MAX_SECONDEN", "150"))
GEVOELIG = re.compile(r"\b([A-Z]{2}\d{2}[ ]?(\d{4}[ ]?){2,4}\d{0,4}|[A-Z]{1,2}\d{6,8})\b")  # IBAN of paspoortachtig

TOOLS = [
    {"type": "function", "name": "noteer_antwoord",
     "description": "Leg vast wat Mehdi antwoordt of beslist, kort en in zijn eigen woorden. Nooit gevoelige "
                    "gegevens zoals een paspoortnummer, rekeningnummer, wachtwoord of code.",
     "parameters": {"type": "object", "properties": {"antwoord": {"type": "string"}}, "required": ["antwoord"]}},
    {"type": "function", "name": "ophangen",
     "description": "Beeindig het gesprek, nadat je in een zin bevestigd hebt wat je doorgeeft.",
     "parameters": {"type": "object", "properties": {}}},
]


def nu():
    return datetime.now(timezone.utc).isoformat()


def teken(gid):
    geheim = os.environ.get("MIJNAGENTS_MCP_SECRET", "").encode()
    return hmac.new(geheim, f"stem:{gid}".encode(), hashlib.sha256).hexdigest()[:32]


def db():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def maak_tabel():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS stemgesprek (
            id INTEGER PRIMARY KEY AUTOINCREMENT, zin TEXT NOT NULL, context TEXT DEFAULT '', wie TEXT DEFAULT '',
            twilio_sid TEXT DEFAULT '', status TEXT DEFAULT 'gepland', antwoord TEXT DEFAULT '',
            verslag TEXT DEFAULT '', ts TEXT NOT NULL, ts_eind TEXT DEFAULT '')""")
        kolommen = {r[1] for r in c.execute("PRAGMA table_info(stemgesprek)")}
        for naam, soort in (("model", "TEXT DEFAULT ''"), ("tokens", "TEXT DEFAULT ''"), ("openai_usd", "REAL"),
                            ("twilio_usd", "REAL"), ("duur_s", "INTEGER")):
            if naam not in kolommen:
                c.execute(f"ALTER TABLE stemgesprek ADD COLUMN {naam} {soort}")


def instructies(zin, context):
    return (
        "Je bent De Bode, de telefonische assistent van Mehdi Chegini. Je belt hem omdat een van zijn agents "
        "vastzit en hem nodig heeft. Spreek Nederlands zoals in Vlaanderen, kort, vriendelijk en zakelijk. "
        "Zoals bij elk telefoongesprek neemt Mehdi op en zegt hij eerst iets, meestal 'hallo'. Dat is een "
        "begroeting, geen antwoord en geen vraag. Antwoord daarop met 'Hallo Mehdi, met De Bode.' en daarna "
        f"deze zin, woord voor woord en zonder een woord te veranderen: \"{zin}\" Vraag daarna in een korte "
        "zin wat hij wil dat de agent doet. "
        "Zegt hij niets, begin dan zelf op dezelfde manier. Zegt hij later nog eens alleen 'hallo' of 'ja', "
        "herhaal dan niet alles maar vraag kort of hij je hoort en wat de agent moet doen. Luister. "
        "Zodra hij een antwoord of beslissing geeft, zeg je in een zin wat je aan de agent doorgeeft en neem je "
        "afscheid, bijvoorbeeld: 'Goed, ik laat de agent weten dat je het zelf invult. Tot straks.' Praat niet over "
        "wat je zelf doet (zeg nooit 'ik noteer' of 'ik bevestig'). Roep in datzelfde antwoord noteer_antwoord aan "
        "met zijn antwoord in zijn eigen woorden, en daarna ophangen. "
        "Zegt hij dat hij het zelf doet of dat hij later terugkomt, noteer dat ook. "
        "Vraag nooit naar gevoelige gegevens (paspoortnummer, rekeningnummer, wachtwoord, codes). Noemt hij ze "
        "toch, noteer ze NIET en zeg dat hij ze zelf op het scherm moet invullen. Verzin niets en beloof niets "
        "wat de agent niet kan. Als hij niets zegt of het niet duidelijk is, vraag het een keer opnieuw en hang "
        "dan op. " + (f"Achtergrond voor jou, niet voorlezen tenzij hij ernaar vraagt: {context}" if context else "")
    )


def telegram(tekst):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if not (tok and chat):
        return
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                     json.dumps({"chat_id": chat, "text": tekst[:3900]}).encode(),
                                     {"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=15).close()
    except Exception:  # noqa: BLE001
        pass


def log(tekst, detail=""):
    with db() as c:
        c.execute("INSERT INTO logboek(naam, onderwerp, stap, tekst, detail, ts) VALUES(?,?,?,?,?,?)",
                  ("bode", "Mehdi geroepen", "stem", tekst, detail, nu()))
    print(f"{nu()} stem: {tekst}", flush=True)


class Gesprek:
    def __init__(self, twilio_ws, rij):
        self.tw = twilio_ws
        self.rij = rij
        self.stream_sid = ""
        self.oa = None
        self.verslag = []          # wat de stem zei en wat genoteerd werd
        self.antwoord = ""
        self.ophangen = False
        self.marks = 0
        self.laatste_mark = ""
        self.terug = set()         # marks die Twilio al afspeelde
        self.usage = {}            # opgetelde tokens van alle antwoorden, voor de kosten
        self.ophang_na_mark = 0    # het aantal marks op het moment dat ophangen gevraagd werd
        self.audio_na_ophang = False   # sprak het model nog na de ophang-vraag (de bevestiging)?
        self.mehdi_sprak = False       # zei Mehdi al iets (meestal 'hallo')?
        self.marks_bij_antwoord = 0    # aantal marks bij de start van het lopende antwoord
        self.begonnen = False          # is De Bode al beginnen spreken?
        self.einde = asyncio.Event()

    def misschien_einde(self):
        """Ophangen pas als de bevestiging NA de ophang-vraag volledig afgespeeld is (Twilio stuurt de mark
        terug). Test 26-09: het model vroeg noteren en ophangen in hetzelfde antwoord; toen hing de oude code
        meteen op, zonder bevestiging. Zegt het model na de ophang-vraag niets meer, dan hangt de wachter
        in ophang_wachter() na OPHANG_WACHT seconden toch op."""
        if self.ophangen and self.marks > self.ophang_na_mark and self.laatste_mark in self.terug:
            self.einde.set()

    def vraag_ophangen(self):
        """Ophangen na de zin van het lopende antwoord (de afscheidszin), niet pas na een volgende zin."""
        if self.ophangen:
            return
        self.ophangen = True
        self.ophang_na_mark = self.marks_bij_antwoord
        taak = asyncio.create_task(self.ophang_wachter())
        ACHTERGROND.add(taak)
        taak.add_done_callback(ACHTERGROND.discard)

    async def ophang_wachter(self):
        """Vangnet. Begint het model na de ophang-vraag niet meer te spreken, dan na OPHANG_WACHT seconden
        ophangen. Spreekt het wel (test 26-09: de bevestiging liep nog toen de oude wachter ophing), dan wacht
        misschien_einde() op de laatste mark, met hoogstens 25 seconden extra als noodrem."""
        await asyncio.sleep(OPHANG_WACHT)
        if not self.audio_na_ophang and self.marks <= self.ophang_na_mark:   # geen afscheidszin gezegd
            self.einde.set()
            return
        await asyncio.sleep(25)
        self.einde.set()

    async def naar_twilio(self, bericht):
        if not self.tw.closed:
            await self.tw.send_json(bericht)

    async def naar_openai(self, bericht):
        if self.oa is not None and not self.oa.closed:
            await self.oa.send_json(bericht)

    async def start_openai(self, sessie):
        basis = os.environ.get("OPENAI_REALTIME_URL", "wss://api.openai.com/v1/realtime")
        self.oa = await sessie.ws_connect(f"{basis}?model={MODEL}",
                                          headers={"Authorization": f"Bearer {sleutel()}"}, heartbeat=20)
        await self.naar_openai({"type": "session.update", "session": {
            "type": "realtime", "model": MODEL, "output_modalities": ["audio"],
            "instructions": instructies(self.rij["zin"], self.rij["context"]),
            "audio": {"input": {"format": {"type": "audio/pcmu"}, "turn_detection": {"type": "server_vad", "silence_duration_ms": 700,
                                                                                         "interrupt_response": False}},
                      "output": {"format": {"type": "audio/pcmu"}, "voice": STEM}},
            "tools": TOOLS, "tool_choice": "auto"}})
        # Niet meteen spreken: wachten op Mehdi's 'hallo' (de spraakdetectie start dan zelf het antwoord).
        # Test 26-09: De Bode sprak meteen, Mehdi's 'hallo' viel erdoorheen en bracht hem in de war.
        taak = asyncio.create_task(self.zelf_beginnen())
        ACHTERGROND.add(taak)
        taak.add_done_callback(ACHTERGROND.discard)

    async def zelf_beginnen(self):
        """Zegt Mehdi binnen EERSTE_WACHT seconden niets (voicemail, stil opgenomen), dan begint De Bode zelf."""
        await asyncio.sleep(EERSTE_WACHT)
        if not self.mehdi_sprak and not self.begonnen:
            self.begonnen = True
            await self.naar_openai({"type": "response.create"})

    async def functie(self, naam, call_id, args):
        if naam == "noteer_antwoord":
            antwoord = str((args or {}).get("antwoord", "")).strip()[:500]
            if GEVOELIG.search(antwoord):
                antwoord = "(Mehdi noemde gevoelige gegevens; niet genoteerd. Hij vult ze zelf in.)"
            self.antwoord = antwoord
            with db() as c:
                c.execute("UPDATE stemgesprek SET antwoord=?, status='beantwoord' WHERE id=?", (antwoord, self.rij["id"]))
            telegram(f"Mehdi antwoordde De Bode:\n\n{antwoord}\n\n(op: {self.rij['zin']})")
            log(f"Mehdi antwoordde: {antwoord[:120]}", self.rij["zin"])
            uitkomst = {"genoteerd": True}
        elif naam == "ophangen":
            self.vraag_ophangen()
            uitkomst = {"ophangen": True}
        else:
            uitkomst = {"fout": "onbekende functie"}
        await self.naar_openai({"type": "conversation.item.create",
                                "item": {"type": "function_call_output", "call_id": call_id, "output": json.dumps(uitkomst)}})

    async def lees_openai(self):
        async for m in self.oa:
            if m.type != WSMsgType.TEXT:
                break
            e = json.loads(m.data)
            soort = e.get("type", "")
            if soort == "input_audio_buffer.speech_started":
                self.mehdi_sprak = True
            elif soort == "response.created":
                self.begonnen = True
                self.marks_bij_antwoord = self.marks   # marks voor dit antwoord: zo telt de afscheidszin mee
            if soort == "response.output_audio.delta" and self.stream_sid:
                if self.ophangen:
                    self.audio_na_ophang = True
                await self.naar_twilio({"event": "media", "streamSid": self.stream_sid, "media": {"payload": e["delta"]}})
            elif soort == "response.output_audio.done" and self.stream_sid:
                self.marks += 1
                self.laatste_mark = f"m{self.marks}"
                await self.naar_twilio({"event": "mark", "streamSid": self.stream_sid, "mark": {"name": self.laatste_mark}})
            # Onderbreken staat uit (interrupt_response false): test 26-09 sneed een "hallo" bij het opnemen de
            # openingszin af. De zinnen van De Bode zijn kort; wat Mehdi intussen zegt, wordt daarna beantwoord.
            elif soort == "response.output_audio_transcript.done":
                self.verslag.append("Bode: " + e.get("transcript", ""))
            elif soort == "response.done":
                tel_op(self.usage, (e.get("response") or {}).get("usage"))
                namen = []
                for item in (e.get("response") or {}).get("output") or []:
                    if item.get("type") == "function_call":
                        try:
                            args = json.loads(item.get("arguments") or "{}")
                        except ValueError:
                            args = {}
                        await self.functie(item.get("name"), item.get("call_id"), args)
                        namen.append(item.get("name"))
                # Pas na ALLE functieresultaten een nieuw antwoord vragen: zo spreekt het model de bevestiging
                # uit, ook als het noteren en ophangen in hetzelfde antwoord vroeg.
                if namen:
                    print(f"{nu()} stem: functies {namen}", flush=True)
                # Met 'ophangen' in dit antwoord is de afscheidszin al gezegd: geen nieuw antwoord vragen.
                if namen and "ophangen" not in namen:
                    await self.naar_openai({"type": "response.create"})
                # Test met Mehdi 26-09: na het noteren zei De Bode 'Tot straks' maar vroeg niet om op te hangen;
                # de lijn bleef open. Is het antwoord al genoteerd en sprak De Bode daarna een zin zonder nieuwe
                # functie, dan was dat het afscheid: ophangen na die zin.
                elif not namen and self.antwoord and self.marks > self.marks_bij_antwoord:
                    self.vraag_ophangen()
                self.misschien_einde()
            elif soort == "error":
                log(f"OpenAI-fout: {json.dumps(e.get('error'))[:200]}")

    async def lees_twilio(self):
        async for m in self.tw:
            if m.type != WSMsgType.TEXT:
                break
            e = json.loads(m.data)
            soort = e.get("event")
            if soort == "media":
                await self.naar_openai({"type": "input_audio_buffer.append", "audio": e["media"]["payload"]})
            elif soort == "mark":
                self.terug.add((e.get("mark") or {}).get("name", ""))
                self.misschien_einde()   # het laatste stuk stem is afgespeeld: nu ophangen
            elif soort == "stop":
                self.einde.set()
                break


async def twilio_prijs(gid, sid):
    """Twilio zet de prijs van een oproep pas een paar minuten na het einde; dan ophalen en bewaren."""
    if not sid:
        return
    acc = os.environ.get("TWILIO_ACCOUNT_SID", "")
    gebruiker = os.environ.get("TWILIO_API_KEY_SID") or acc
    geheim = os.environ.get("TWILIO_API_KEY_SECRET") or os.environ.get("TWILIO_AUTH_TOKEN", "")
    kop = {"Authorization": "Basic " + base64.b64encode(f"{gebruiker}:{geheim}".encode()).decode()}
    for wacht in TWILIO_PRIJS_WACHT:
        await asyncio.sleep(wacht)
        try:
            async with ClientSession() as s:
                async with s.get(f"https://api.twilio.com/2010-04-01/Accounts/{acc}/Calls/{sid}.json",
                                 headers=kop, timeout=30) as r:
                    d = await r.json()
            if d.get("price") is not None:
                with db() as c:
                    c.execute("UPDATE stemgesprek SET twilio_usd=? WHERE id=?", (abs(float(d["price"])), gid))
                return
        except Exception:  # noqa: BLE001
            pass


async def stroom(request):
    tw = web.WebSocketResponse(heartbeat=20)
    await tw.prepare(request)
    rij, gesprek, begin = None, None, time.time()
    async with ClientSession() as sessie:
        try:
            async for m in tw:
                if m.type != WSMsgType.TEXT:
                    break
                e = json.loads(m.data)
                if e.get("event") != "start":
                    continue
                p = (e.get("start") or {}).get("customParameters") or {}
                gid = str(p.get("g", ""))
                if not gid.isdigit() or not hmac.compare_digest(str(p.get("t", "")), teken(gid)):
                    print(f"{nu()} stem: ongeldig teken, stroom geweigerd", flush=True)
                    break
                with db() as c:
                    rij = c.execute("SELECT * FROM stemgesprek WHERE id=?", (int(gid),)).fetchone()
                    if not rij or rij["status"] not in ("gepland", "gebeld"):
                        rij = None
                        break
                    c.execute("UPDATE stemgesprek SET status='in gesprek' WHERE id=?", (int(gid),))
                gesprek = Gesprek(tw, rij)
                gesprek.stream_sid = e["start"]["streamSid"]
                await gesprek.start_openai(sessie)
                begin = time.time()
                log(f"gesprek {gid} gestart met {MODEL}", rij["zin"])
                taken = [asyncio.create_task(gesprek.lees_openai()), asyncio.create_task(gesprek.lees_twilio()),
                         asyncio.create_task(gesprek.einde.wait())]
                done, pending = await asyncio.wait(taken, timeout=MAX_SECONDEN, return_when=asyncio.FIRST_COMPLETED)
                for t in pending:
                    t.cancel()
                break
        except Exception as e:  # noqa: BLE001
            log(f"gesprek mislukt: {type(e).__name__}: {str(e)[:150]}")
        finally:
            if gesprek and gesprek.oa is not None:
                await gesprek.oa.close()
            if rij:
                usage = gesprek.usage if gesprek else {}
                oa_usd = kosten_usd(MODEL, usage) if usage else 0.0
                with db() as c:
                    status = "beantwoord" if gesprek and gesprek.antwoord else "zonder antwoord"
                    c.execute("UPDATE stemgesprek SET status=?, verslag=?, ts_eind=?, model=?, tokens=?, openai_usd=?, "
                              "duur_s=? WHERE id=?",
                              (status, "\n".join(gesprek.verslag if gesprek else [])[:4000], nu(), MODEL,
                               json.dumps(usage), oa_usd, int(time.time() - begin), rij["id"]))
                log(f"gesprek {rij['id']} {status}: {int(time.time() - begin)} s, OpenAI {oa_usd:.4f} USD "
                    f"({usage.get('input_tokens', 0)} in, {usage.get('output_tokens', 0)} uit)", rij["zin"])
                taak = asyncio.create_task(twilio_prijs(rij["id"], rij["twilio_sid"]))
                ACHTERGROND.add(taak)
                taak.add_done_callback(ACHTERGROND.discard)
            await tw.close()
    return tw


async def gezond(_request):
    return web.json_response({"ok": True, "model": MODEL, "sleutel": bool(sleutel())})


def app():
    maak_tabel()
    a = web.Application()
    a.router.add_get("/stem/ws", stroom)
    a.router.add_get("/gezond", gezond)
    return a


if __name__ == "__main__":
    web.run_app(app(), host="0.0.0.0", port=int(os.environ.get("PORT", "3040")))
