#!/usr/bin/env python3
"""De Belwacht Xelion (privé-communicatie, 31-10-2026): leest elk uur de oproepen van Mehdi in de Xelion-centrale en
schrijft per oproep een privérij in de gesprekkentabel: wie, wanneer, hoe lang, in of uit, gemist. Nooit een opname,
nooit een transcript, nooit een contact wijzigen.

Xelion zelf leest hij niet: de communicatie-app (globaal-communicatie, app-communicatie) spiegelt de gesprekken van de
centrale al elke vijf minuten in Postgres (communicatie.xelion_communicatie, sinds 23-09-2026 twaalf maanden terug). Deze
wacht vraagt alleen die spiegel, binnen de container van de app (zijn DATABASE_URL, alleen lezen), voor de gebruiker en
de gsm-lijn van Mehdi. Zo komt er geen tweede login bij Xelion (die telt mislukte logins en vergrendelt de account).

Rijen: xelion:<oid> (bron xelion, privé), een oproep zonder gesprek met dubbel_van buiten:gemist, en dekking:xelion:<dag>
voor elke voorbije dag waarna de spiegel nog foutloos liep: zo is een dag zonder oproep een echte 0, en een dag die de
spiegel niet zag onbekend. Een Xelion-oproep die ook als iPhone-oproep op het bord staat (doorgeschakeld naar de gsm),
krijgt dubbel_van telefoon:<uniek>: de iPhone-rij telt, de Xelion-rij niet (TEL-6, T-0084).

    xelion_wacht.py           een ronde (cron op de VM, elk uur)
    xelion_wacht.py --droog   per dag de aantallen tonen; niets naar het bord
    xelion_wacht.py --inhaal-vanaf 2026-10-01
                              eenmalig vanaf die dag lezen (TEL-2, hoogstens 60 dagen terug; de spiegel houdt er 12
                              maanden); ook --van
"""
import argparse
import json
import os
import secrets
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import bordstand  # noqa: E402
import dagvaststelling as V  # noqa: E402
import mac_gesprekken as M  # noqa: E402

NAAM = "xelion-wacht"
KANAAL = "xelion"
TAAK = "Xelion-oproepen uit de databank lezen"   # met 'databank': zo ziet De Dagbundelaar dat Xelion aangesloten is
CONTAINER = os.environ.get("XELION_CONTAINER", "appportal-app-communicatie-1")
GEBRUIKER = os.environ.get("XELION_GEBRUIKER", "Mehdi")             # xelion_gebruiker.gebruikersnaam
LIJN = os.environ.get("XELION_LIJN", "Mehdi Chegini gsm")           # xelion_lijn.naam
SAMEN = timedelta(minutes=2)    # TEL-6: zo dicht bij elkaar begint dezelfde oproep in Xelion en op de iPhone
ag = bord.Agent(NAAM)

# De vraag loopt in de container van de communicatie-app (node en pg staan daar al). Alleen SELECT, met parameters.
VRAAG_JS = r"""
const {Client} = require('pg');
let invoer = '';
process.stdin.on('data', d => invoer += d).on('end', async () => {
  const p = JSON.parse(invoer);
  const c = new Client({connectionString: process.env.DATABASE_URL});
  try {
    await c.connect();
    await c.query('BEGIN READ ONLY');
    const wie = await c.query(
      "SELECT (SELECT oid FROM communicatie.xelion_gebruiker WHERE gebruikersnaam = $1 LIMIT 1) AS gebruiker, " +
      "(SELECT oid FROM communicatie.xelion_lijn WHERE naam = $2 LIMIT 1) AS lijn", [p.gebruiker, p.lijn]);
    const g = wie.rows[0] || {};
    const rijen = await c.query(
      "SELECT oid, datum, richting, duur_sec, beantwoord, status, extern_nummer, extern_naam " +
      "FROM communicatie.xelion_communicatie WHERE datum >= $1 AND datum < $2 " +
      "AND ((gebruiker_oid IS NOT NULL AND gebruiker_oid = $3) OR (lijn_oid IS NOT NULL AND lijn_oid = $4)) " +
      "ORDER BY datum, oid", [p.van, p.tot, g.gebruiker || '', g.lijn || '']);
    const sync = await c.query("SELECT laatste_run, ok, comm_nieuwste, comm_fout FROM communicatie.xelion_sync LIMIT 1");
    await c.query('ROLLBACK');
    console.log(JSON.stringify({gebruiker: g.gebruiker || null, lijn: g.lijn || null, rijen: rijen.rows,
                                sync: sync.rows[0] || null}));
  } catch (e) {
    console.log(JSON.stringify({fout: e.constructor.name}));
  } finally {
    await c.end().catch(() => {});
  }
});
"""


def spiegel_lezen(van, tot, docker="docker"):
    """De oproepen van Mehdi tussen van en tot (UTC) en de stand van de spiegel, uit de communicatie-app."""
    r = subprocess.run([docker, "exec", "-i", CONTAINER, "node", "-e", VRAAG_JS],
                       input=json.dumps({"van": van.isoformat(), "tot": tot.isoformat(), "gebruiker": GEBRUIKER,
                                         "lijn": LIJN}),
                       capture_output=True, text=True, timeout=120, check=False)
    try:
        uit = json.loads((r.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise M.MacFout(f"spiegel van Xelion onleesbaar (exit {r.returncode})",
                        "De Xelion-spiegel in de communicatie-app is niet leesbaar") from None
    if uit.get("fout"):
        raise M.MacFout(f"spiegel van Xelion: {uit['fout']}", "De Xelion-spiegel in de communicatie-app is niet leesbaar")
    if not uit.get("gebruiker") and not uit.get("lijn"):
        raise M.MacFout("gebruiker en lijn van Mehdi niet gevonden in Xelion",
                        "Gebruiker of gsm-lijn van Mehdi staat niet (meer) in de Xelion-spiegel", wie="mehdi")
    return uit


def _tijd(x):
    t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def rijen_van(spiegel, dagenlijst, onbekend_als_nummer=True):
    """De rijen voor de gesprekkentabel. Geeft (rijen, info) met info['gemist'] en info['gedekt']: de dagen waarna de
    spiegel nog foutloos liep."""
    rijen = []
    for x in spiegel.get("rijen") or []:
        moment = _tijd(x["datum"])
        dag = M.dag_van(moment)
        if dag not in dagenlijst:
            continue
        duur = float(x.get("duur_sec") or 0)
        nummer = M.schoon(x.get("extern_nummer") or "")
        persoon = M.schoon(x.get("extern_naam") or "") or (nummer if onbekend_als_nummer and nummer else
                                                             "onbekend nummer" if nummer else "nummer verborgen")
        richting = "uitgaand" if str(x.get("richting") or "") == "uitgaand" else "inkomend"
        gesprek = duur > 0 and bool(x.get("beantwoord"))
        thema = f"Xelion, {richting}" + ("" if gesprek else (", niet beantwoord" if richting == "uitgaand" else ", gemist"))
        oid = "".join(c for c in str(x.get("oid") or "") if c.isalnum())
        if not oid:
            continue
        rijen.append(M._rij(f"xelion:{oid}", dag, M.start_van(moment), M.minuten(duur) if gesprek else 0, persoon,
                            thema, "xelion", "" if gesprek else M.GEMIST))
    sync = spiegel.get("sync") or {}
    gedekt = []
    if sync.get("ok") and not sync.get("comm_fout") and sync.get("laatste_run"):
        laatste = _tijd(sync["laatste_run"])
        gedekt = [d for d in dagenlijst if laatste >= M.daggrens(M.volgende(d))]
    rijen += [M._rij(f"dekking:{KANAAL}:{d}", d, "", 0, "", "gelezen", "dekking", M.DEKKING) for d in gedekt]
    return rijen, {"gedekt": gedekt, "gemist": sum(1 for r in rijen if r["dubbel_van"] == M.GEMIST)}


def terug_lokaal(kanaal, van, tot):
    return bordstand.gesprekken(kanaal, van, tot)


def telefoon_lokaal(van, tot, db=None):
    """De iPhone-oproepen van De Belwacht op het bord (datum van tot en met tot): uniek, datum, start, minuten en
    dubbel_van, nooit wie of het thema. Alleen lezen."""
    con = sqlite3.connect(f"file:{db or bordstand.DB}?mode=ro", uri=True)
    try:
        rijen = con.execute("SELECT uniek, datum, start, minuten, COALESCE(dubbel_van, '') FROM gesprek_log "
                            "WHERE datum BETWEEN ? AND ? AND substr(uniek, 1, 9) = 'telefoon:'", (van, tot)).fetchall()
    finally:
        con.close()
    return [dict(zip(("uniek", "datum", "start", "minuten", "dubbel_van"), r)) for r in rijen]


def ontdubbel(rijen, telefoon):
    """TEL-6 (T-0084): een Xelion-oproep die ook als iPhone-oproep binnenkwam, telt een keer; de iPhone-rij leidt. Een
    paar is: beide een gesprek of beide zonder gesprek, het begin hoogstens SAMEN uit elkaar en ongeveer even lang
    (hoogstens een minuut of een vijfde verschil). Elke iPhone-rij hoort bij hoogstens een Xelion-rij, de dichtste wint.
    Zonder paar verandert niets. Geeft het aantal Xelion-rijen dat dubbel werd."""
    vrij = [t for t in telefoon if t.get("dubbel_van") in ("", M.GEMIST)]
    n = 0
    for x in sorted((x for x in rijen if x["bron"] == KANAAL and x["dubbel_van"] in ("", M.GEMIST)),
                    key=lambda x: V.gesprek_venster(x)[0]):
        begin, m = V.gesprek_venster(x)[0], int(x["minuten"] or 0)
        kandidaten = []
        for t in vrij:
            tm = int(t.get("minuten") or 0)
            afstand = abs(V.gesprek_venster(t)[0] - begin)
            if (t["dubbel_van"] == "") == (x["dubbel_van"] == "") and afstand <= SAMEN \
                    and abs(tm - m) <= max(1, max(tm, m) / 5):
                kandidaten.append((afstand, t["uniek"], t))
        if kandidaten:
            _, uniek, t = min(kandidaten, key=lambda k: k[:2])
            vrij.remove(t)
            x["dubbel_van"] = uniek
            n += 1
    return n


def werk(r, ronde_id, lezer=spiegel_lezen, terug=terug_lokaal, nu=None, vanaf=None, telefoon=telefoon_lokaal):
    """Een ronde: de laatste 14 dagen, of met vanaf (TEL-2) eenmalig vanaf die dag."""
    M.grenzen_of_stop(r.werkwijze, bord.grenzen)
    r.bron(f"ronde-id-{ronde_id}", "")
    nu = nu or datetime.now(timezone.utc)
    dagen = M.dagen(nu, M.inhaal_grens(None, vanaf))
    try:
        spiegel = lezer(M.daggrens(dagen[0]), M.daggrens(M.volgende(dagen[-1])))
        rijen, info = rijen_van(spiegel, dagen)
        dubbel = ontdubbel(rijen, telefoon(dagen[0], dagen[-1]))
        ag.prive(M.maskerwoorden(rijen))
        vervallen = M.schrijf_en_lees_terug(KANAAL, rijen, dagen[0], dagen[-1], bord.call, terug)
    except M.MacFout as e:
        r.nood(e.nood, wie=e.wie)
        raise
    gisteren = dagen[-2]
    oproepen = [x for x in rijen if x["datum"] == gisteren and x["bron"] == KANAAL]
    gesprek = [x for x in oproepen if not x["dubbel_van"]]
    gemist = [x for x in oproepen if x["dubbel_van"] == M.GEMIST]
    r.detail = (f"privé; {len(dagen)} dagen gelezen ({dagen[0]} tot {dagen[-1]}); gisteren {len(gesprek)} oproepen, "
                f"{sum(x['minuten'] for x in gesprek)} min, {len(gemist)} gemist; {dubbel} ook als iPhone-oproep; "
                f"dekking tot {max(info['gedekt']) if info['gedekt'] else 'geen'}; {len(rijen)} rijen, "
                f"{vervallen} vervallen; ronde-id:{ronde_id}")
    for dag in dagen[-2:]:
        n = [x for x in rijen if x["datum"] == dag and x["bron"] == KANAAL]
        ag.log(f"dag {dag}", "gelezen", f"{len([x for x in n if not x['dubbel_van']])} oproepen, "
               f"{len([x for x in n if x['dubbel_van'] == M.GEMIST])} gemist, "
               f"{len([x for x in n if x['dubbel_van'].startswith('telefoon:')])} ook op de iPhone")
    if not info["gedekt"]:
        r.nood("De Xelion-spiegel in de communicatie-app liep niet foutloos: staat XELION_ENABLED aan?", wie="claude-code")
    return info


def droog(vanaf=None):
    nu = datetime.now(timezone.utc)
    dagen = M.dagen(nu, M.inhaal_grens(None, vanaf))
    rijen, info = rijen_van(spiegel_lezen(M.daggrens(dagen[0]), M.daggrens(M.volgende(dagen[-1]))), dagen)
    ontdubbel(rijen, telefoon_lokaal(dagen[0], dagen[-1]))
    for dag in dagen:
        n = [x for x in rijen if x["datum"] == dag and x["bron"] == KANAAL]
        print(f"{dag}: {len([x for x in n if not x['dubbel_van']])} oproepen, "
              f"{len([x for x in n if x['dubbel_van'] == M.GEMIST])} gemist, "
              f"{len([x for x in n if x['dubbel_van'].startswith('telefoon:')])} ook op de iPhone"
              f"{'' if dag in info['gedekt'] else ', niet gedekt'}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="De Belwacht Xelion: de Xelion-oproepen van Mehdi lezen.")
    p.add_argument("--droog", action="store_true", help="per dag de aantallen tonen, niets naar het bord")
    p.add_argument("--inhaal-vanaf", "--van", type=M.inhaal_vanaf, metavar="JJJJ-MM-DD",
                   help="eenmalig vanaf die dag lezen (hoogstens 60 dagen terug)")
    a = p.parse_args(argv)
    if a.droog:
        return droog(a.inhaal_vanaf)
    ronde_id = secrets.token_hex(16)
    try:
        with ag.ronde(TAAK) as r:
            werk(r, ronde_id, vanaf=a.inhaal_vanaf)
    except (M.MacFout, bord.RondeGestopt) as e:
        print(f"ronde mislukt: {e}", file=sys.stderr)
        return 1
    print(f"{datetime.now().isoformat(timespec='seconds')} De Belwacht Xelion: ronde gelukt, ronde-id:{ronde_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
