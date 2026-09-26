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
MODEL = os.environ.get("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1")
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


def instructies(zin, context):
    return (
        "Je bent De Bode, de telefonische assistent van Mehdi Chegini. Je belt hem omdat een van zijn agents "
        "vastzit en hem nodig heeft. Spreek Nederlands zoals in Vlaanderen, kort, vriendelijk en zakelijk. "
        f"Begin meteen met deze zin, woord voor woord: \"{zin}\" "
        "Vraag daarna in een korte zin wat hij wil dat de agent doet. Luister. "
        "Zodra hij een antwoord of beslissing geeft, roep je noteer_antwoord aan met zijn antwoord in zijn eigen "
        "woorden, bevestig je in een zin wat je doorgeeft, en roep je ophangen aan. "
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
        self.einde = asyncio.Event()

    def misschien_einde(self):
        """Ophangen pas als de laatste zin volledig afgespeeld is (Twilio stuurt de mark terug)."""
        if self.ophangen and (not self.laatste_mark or self.laatste_mark in self.terug):
            self.einde.set()

    async def naar_twilio(self, bericht):
        if not self.tw.closed:
            await self.tw.send_json(bericht)

    async def naar_openai(self, bericht):
        if self.oa is not None and not self.oa.closed:
            await self.oa.send_json(bericht)

    async def start_openai(self, sessie):
        sleutel = os.environ.get("OPENAI_API_KEY", "")
        basis = os.environ.get("OPENAI_REALTIME_URL", "wss://api.openai.com/v1/realtime")
        self.oa = await sessie.ws_connect(f"{basis}?model={MODEL}",
                                          headers={"Authorization": f"Bearer {sleutel}"}, heartbeat=20)
        await self.naar_openai({"type": "session.update", "session": {
            "type": "realtime", "model": MODEL, "output_modalities": ["audio"],
            "instructions": instructies(self.rij["zin"], self.rij["context"]),
            "audio": {"input": {"format": {"type": "audio/pcmu"}, "turn_detection": {"type": "server_vad", "silence_duration_ms": 700}},
                      "output": {"format": {"type": "audio/pcmu"}, "voice": STEM}},
            "tools": TOOLS, "tool_choice": "auto"}})
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
            self.ophangen = True
            uitkomst = {"ophangen": True}
        else:
            uitkomst = {"fout": "onbekende functie"}
        await self.naar_openai({"type": "conversation.item.create",
                                "item": {"type": "function_call_output", "call_id": call_id, "output": json.dumps(uitkomst)}})
        if naam != "ophangen":
            await self.naar_openai({"type": "response.create"})

    async def lees_openai(self):
        async for m in self.oa:
            if m.type != WSMsgType.TEXT:
                break
            e = json.loads(m.data)
            soort = e.get("type", "")
            if soort == "response.output_audio.delta" and self.stream_sid:
                await self.naar_twilio({"event": "media", "streamSid": self.stream_sid, "media": {"payload": e["delta"]}})
            elif soort == "response.output_audio.done" and self.stream_sid:
                self.marks += 1
                self.laatste_mark = f"m{self.marks}"
                await self.naar_twilio({"event": "mark", "streamSid": self.stream_sid, "mark": {"name": self.laatste_mark}})
            elif soort == "input_audio_buffer.speech_started" and self.stream_sid:
                await self.naar_twilio({"event": "clear", "streamSid": self.stream_sid})
            elif soort == "response.output_audio_transcript.done":
                self.verslag.append("Bode: " + e.get("transcript", ""))
            elif soort == "response.done":
                for item in (e.get("response") or {}).get("output") or []:
                    if item.get("type") == "function_call":
                        try:
                            args = json.loads(item.get("arguments") or "{}")
                        except ValueError:
                            args = {}
                        await self.functie(item.get("name"), item.get("call_id"), args)
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


async def stroom(request):
    tw = web.WebSocketResponse(heartbeat=20)
    await tw.prepare(request)
    rij, gesprek = None, None
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
                with db() as c:
                    status = "beantwoord" if gesprek and gesprek.antwoord else "zonder antwoord"
                    c.execute("UPDATE stemgesprek SET status=?, verslag=?, ts_eind=? WHERE id=?",
                              (status, "\n".join(gesprek.verslag if gesprek else [])[:4000], nu(), rij["id"]))
                if not (gesprek and gesprek.antwoord):
                    log(f"gesprek {rij['id']} zonder antwoord beeindigd", rij["zin"])
            await tw.close()
    return tw


async def gezond(_request):
    return web.json_response({"ok": True, "model": MODEL, "sleutel": bool(os.environ.get("OPENAI_API_KEY"))})


def app():
    maak_tabel()
    a = web.Application()
    a.router.add_get("/stem/ws", stroom)
    a.router.add_get("/gezond", gezond)
    return a


if __name__ == "__main__":
    web.run_app(app(), host="0.0.0.0", port=int(os.environ.get("PORT", "3040")))
