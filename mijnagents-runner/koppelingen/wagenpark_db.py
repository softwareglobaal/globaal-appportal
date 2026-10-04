"""De Wagenparkwacht en de wagenpark-app in Vermogen (schema vermogen, migratie 187).

Mehdi, 05-10-2026: een functionerende wagenpark-app zoals Odoo Fleet op onze Authentik. De app
(vermogen.globaal.be/wagenpark) is de plek waar een mens wagens, onderhoud, km-standen, bestuurders,
contracten en notities bijhoudt. De agent werkt eromheen:

  lezen()     wat een mens in de app invoerde of aanpaste, zodat de agent daarvan uitgaat;
  schrijven() wat de agent vond (facturen, boekhouding, tankkaarten, signalen), alleen in rijen met
              een eigen sleutel, en nooit in een veld dat een mens aanpaste (voertuig.handmatig).

Toegang zoals koppelingen/organisatie.py: psql in de Postgres-container. Gegevens gaan als JSON
in een dollar-quoted blok mee, nooit in een opdrachtregel.
"""
import hashlib
import json
import os
import re
import subprocess

CONTAINER = os.environ.get("KERN_POSTGRES_CONTAINER", "appportal-postgresql-1")
DB = os.environ.get("KERN_DB", "appportal")
MERKEN = ("Ford", "Citroën", "Opel", "Renault", "Mercedes", "Suzuki", "Mitsubishi", "Toyota", "Volkswagen", "Peugeot")
LICHTE_VRACHT = ("Transit", "Berlingo", "Kangoo", "Sprinter")
VELDEN = ("platen_oud", "plaat_buitenland", "vin", "merk", "model", "categorie", "brandstof", "bouwjaar",
          "eerste_inschrijving", "firma_id", "land", "status", "bestuurder", "keuring_tot", "tankinhoud_l", "dropbox_map")


def _psql(sql):
    gebruiker = subprocess.run(["docker", "exec", CONTAINER, "sh", "-c", "echo $POSTGRES_USER"],
                               capture_output=True, text=True, timeout=30).stdout.strip() or "postgres"
    r = subprocess.run(["docker", "exec", "-i", CONTAINER, "psql", "-U", gebruiker, "-d", DB, "-At", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout


def _blok(data):
    """JSON als dollar-quoted SQL-literal; de tag komt nooit in de gegevens voor."""
    tekst = json.dumps(data, ensure_ascii=False, default=str)
    tag = "wp" + hashlib.sha1(tekst.encode()).hexdigest()[:10]
    return f"${tag}${tekst}${tag}$::jsonb"


def _sleutel(*delen):
    return "wp:" + hashlib.sha1("|".join(str(d) for d in delen).encode()).hexdigest()[:20]


def _getal(s):
    m = re.search(r"(\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)", str(s or ""))
    if not m:
        return None
    x = m.group(1).replace(" ", "")
    if "," in x:
        x = x.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", x):
        x = x.replace(".", "")
    try:
        return float(x)
    except ValueError:
        return None


def _munt(s):
    s = str(s or "").lower()
    return "SRD" if "srd" in s else ("USD" if "usd" in s else "EUR")


def _datum(s):
    """Alleen een volledige datum (JJJJ-MM-DD); al de rest wordt NULL in plaats van een fout."""
    m = re.match(r"\d{4}-\d{2}-\d{2}", str(s or ""))
    return m.group(0) if m else None


def _jaar(s):
    m = re.match(r"(19|20)\d{2}", str(s or ""))
    return int(m.group(0)) if m else None


def voertuig_rij(v):
    """Het register van een wagen als rij voor vermogen.voertuig."""
    mm = (v.get("merk_model") or "").strip()
    merk = next((m for m in MERKEN if mm.lower().startswith(m.lower())), mm.split(" ")[0] if mm else "")
    model = mm[len(merk):].strip() if merk and mm.lower().startswith(merk.lower()) else mm
    return {"plaat": v["plaat"], "platen_oud": ", ".join(v.get("platen_oud") or []),
            "plaat_buitenland": v.get("plaat_suriname") or "", "vin": v.get("chassis") or "",
            "merk": merk, "model": model, "categorie": "N1" if any(x in mm for x in LICHTE_VRACHT) else "M1",
            "brandstof": v.get("brandstof") or "", "bouwjaar": _jaar(v.get("bouwjaar")) or _jaar(v.get("bouwjaar_vin")),
            "eerste_inschrijving": _datum(v.get("eerste_inschrijving")), "firma": v.get("firma") or "",
            "land": v.get("land") or "België", "status": v.get("status") or "in gebruik",
            "bestuurder": v.get("gebruik") or "", "keuring_tot": _datum(v.get("keuring_tot")),
            "tankinhoud_l": v.get("tankinhoud_l") if isinstance(v.get("tankinhoud_l"), int) else None,
            "dropbox_map": (v.get("mappen") or [""])[-1]}


def lezen():
    """{plaat: {veld: waarde (voor velden die een mens aanpaste), 'km': [...], 'diensten': [...], 'bestuurders': [...]}}
    voor alles wat met de hand in de app staat. Leeg als de tabellen er nog niet zijn."""
    sql = """
select coalesce(json_object_agg(v.plaat, json_build_object(
  'handmatig', v.handmatig,
  'velden', (select coalesce(json_object_agg(k, to_jsonb(v) -> k), '{}'::json) from unnest(v.handmatig) k),
  'firma_code', f.code,
  'km', (select coalesce(json_agg(json_build_object('datum', k.datum, 'km', k.km, 'bron', 'manueel')), '[]'::json)
         from vermogen.voertuig_kmstand k where k.voertuig_id = v.id and k.bron = 'manueel' and k.actief),
  'diensten', (select coalesce(json_agg(json_build_object('datum', d.datum, 'soort', d.soort, 'garage', d.leverancier,
         'km', d.km, 'bedrag', case when d.bedrag is null then null else d.bedrag::text || ' ' || d.munt end,
         'omschrijving', d.omschrijving, 'werken', d.werken, 'factuur_pad', d.factuur_pad, 'herkomst', 'manueel')), '[]'::json)
         from vermogen.voertuig_dienst d where d.voertuig_id = v.id and d.bron = 'manueel' and d.actief and d.status = 'uitgevoerd'),
  'bestuurders', (select coalesce(json_agg(json_build_object('naam', b.naam, 'van', b.van, 'tot', b.tot, 'bron', 'manueel')), '[]'::json)
         from vermogen.voertuig_bestuurder b where b.voertuig_id = v.id and b.bron = 'manueel' and b.actief)
)), '{}'::json)
from vermogen.voertuig v left join kern.firma f on f.id = v.firma_id;"""
    try:
        return json.loads(_psql(sql).strip() or "{}")
    except Exception:  # noqa: BLE001  tabellen nog niet gemigreerd of databank weg: de agent werkt verder zoals voor
        return {}


VELD_IN_REGISTER = {"status": "status", "bestuurder": "gebruik", "land": "land", "eerste_inschrijving": "eerste_inschrijving",
                    "keuring_tot": "keuring_tot", "vin": "chassis", "plaat_buitenland": "plaat_suriname", "bouwjaar": "bouwjaar"}


def toepassen(register, mens):
    """Wat een mens in de app aanpaste, gaat voor in het register van de agent (alleen in het geheugen van deze ronde)."""
    for v in register["voertuigen"]:
        m = mens.get(v["plaat"])
        if not m:
            continue
        for veld, waarde in (m.get("velden") or {}).items():
            if veld in VELD_IN_REGISTER and waarde not in (None, ""):
                v[VELD_IN_REGISTER[veld]] = waarde
        if "firma_id" in (m.get("handmatig") or []) and m.get("firma_code"):
            v["firma"] = m["firma_code"]
        v["km"] = (v.get("km") or []) + [k for k in m.get("km") or [] if k.get("datum")]
        v["onderhoud"] = (v.get("onderhoud") or []) + [d for d in m.get("diensten") or [] if d.get("datum")]
        if m.get("bestuurders"):
            v["bestuurders"] = (v.get("bestuurders") or []) + m["bestuurders"]
    return register


def _activiteiten(w):
    """Signalen van de agent voor een wagen uit het dashboard: termijnen, vooruitblik, controles, open vragen."""
    uit = []
    for t in w.get("termijnen") or []:
        if t.get("stand") in ("verlopen", "dringend", "binnenkort") or (t.get("wat", "").startswith("opzeggen") and (t.get("dagen") or 999) <= 60):
            titel = f"{t['wat']} {'verlopen sinds' if (t.get('dagen') or 0) < 0 else 'op'} {t['datum']}"
            uit.append({"soort": "signaal", "titel": titel, "vervaldatum": t["datum"], "sleutel": _sleutel("t", w["plaat"], t["wat"], t["datum"])})
    for b in w.get("vooruitblik") or []:
        if b.get("stand") in ("te laat", "binnenkort") and (b.get("herkomst") == "fabrikant" or b.get("laatst")):
            kost = f", ongeveer {b['kost_eigen_facturen']} EUR volgens eigen facturen" if b.get("kost_eigen_facturen") else ""
            uit.append({"soort": "taak", "titel": f"{b['onderdeel']}: {b['stand']} (verwacht {b['verwacht']}){kost}", "vervaldatum": b["verwacht"],
                        "sleutel": _sleutel("v", w["plaat"], b["onderdeel"], b["verwacht"])})
    for n in w.get("km_nazicht") or []:
        uit.append({"soort": "taak", "titel": f"Kilometerstand {n['km']} op {n['datum']} past niet in de reeks ({n.get('bron') or 'onbekend'}): nakijken",
                    "vervaldatum": None, "sleutel": _sleutel("km", w["plaat"], n["datum"], n["km"])})
    for x in w.get("tankcontrole") or []:
        uit.append({"soort": "taak", "titel": f"Tankcontrole {x['wanneer']}: {x['wat']}", "vervaldatum": None,
                    "sleutel": _sleutel("tank", w["plaat"], x["soort"], x["wanneer"])})
    for q in w.get("open_vragen") or []:
        uit.append({"soort": "taak", "titel": q[:300], "vervaldatum": None, "sleutel": _sleutel("q", w["plaat"], q)})
    return uit


def schrijven(register, dashboard):
    """Alles wat de agent weet naar de app. Geeft een telling terug."""
    wagens = {w["plaat"]: w for w in dashboard.get("wagens") or []}
    voertuigen, diensten, kms, bestuurders, activiteiten = [], [], [], [], []
    for v in register["voertuigen"]:
        p = v["plaat"]
        voertuigen.append(voertuig_rij(v))
        for o in v.get("onderhoud") or []:
            if not _datum(o.get("datum")) or o.get("herkomst") == "manueel":
                continue
            status = "gepland" if o.get("soort") == "offerte" else "uitgevoerd"
            diensten.append({"plaat": p, "datum": o["datum"][:10], "soort": "herstelling" if o.get("soort") == "offerte" else (o.get("soort") or "onderhoud"),
                             "status": status, "leverancier": o.get("garage") or "", "km": o.get("km"), "bedrag": _getal(o.get("bedrag")),
                             "munt": _munt(o.get("bedrag")), "factuurnummer": o.get("factuurnummer") or "", "factuur_pad": o.get("factuur_pad") or "",
                             "werken": o.get("werken") or [], "omschrijving": (o.get("omschrijving") or "")[:500],
                             "bron": o.get("herkomst") or "register",
                             "sleutel": _sleutel("d", p, o["datum"][:10], o.get("soort"), o.get("factuurnummer") or o.get("garage"))})
        for m in v.get("brandstof_maanden") or []:
            diensten.append({"plaat": p, "datum": m["maand"] + "-01", "soort": "brandstof", "status": "uitgevoerd", "leverancier": m.get("leverancier") or "",
                             "km": m.get("km_hoogst"), "bedrag": _getal(m.get("bedrag_excl") or m.get("bedrag_incl")), "munt": "EUR",
                             "factuurnummer": "", "factuur_pad": "", "werken": [],
                             "omschrijving": f"{m.get('liters') or '?'} liter, {m.get('aantal_tankbeurten') or '?'} tankbeurten in {m['maand']}",
                             "bron": "tankkaart", "sleutel": _sleutel("f", p, m["maand"])})
        verdacht = {(n["datum"], n["km"]) for n in (wagens.get(p) or {}).get("km_nazicht") or []}
        for k in v.get("km") or []:
            try:
                km = int(float(k.get("km")))
            except (TypeError, ValueError):
                continue
            if _datum(k.get("datum")) and km > 0 and k.get("bron") != "manueel":
                kms.append({"plaat": p, "datum": k["datum"][:10], "km": km, "bron": k.get("bron") or "agent",
                            "verdacht": (k["datum"][:10], km) in verdacht, "sleutel": _sleutel("k", p, k["datum"][:10], km)})
        for b in v.get("bestuurders") or []:
            if b.get("naam") and b.get("bron") != "manueel":
                bestuurders.append({"plaat": p, "naam": b["naam"][:200], "van": b.get("van") if re.match(r"\d{4}-\d{2}-\d{2}", str(b.get("van") or "")) else None,
                                    "tot": b.get("tot") if re.match(r"\d{4}-\d{2}-\d{2}", str(b.get("tot") or "")) else None,
                                    "omschrijving": (b.get("bron") or "")[:300], "sleutel": _sleutel("b", p, b["naam"], b.get("van"))})
        for a in _activiteiten(dict(wagens.get(p) or {}, plaat=p, open_vragen=v.get("open_vragen") or [])):
            activiteiten.append(dict(a, plaat=p))
    sql = f"""
begin;
select set_config('app.gebruiker', 'De Wagenparkwacht', true);
with r as (select * from jsonb_to_recordset({_blok(voertuigen)}) as x(plaat text, platen_oud text, plaat_buitenland text, vin text, merk text,
    model text, categorie text, brandstof text, bouwjaar int, eerste_inschrijving date, firma text, land text, status text,
    bestuurder text, keuring_tot date, tankinhoud_l int, dropbox_map text))
insert into vermogen.voertuig as v (plaat, platen_oud, plaat_buitenland, vin, merk, model, categorie, brandstof, bouwjaar,
    eerste_inschrijving, firma_id, land, status, bestuurder, keuring_tot, tankinhoud_l, dropbox_map, actief, bijgewerkt_door)
select r.plaat, coalesce(r.platen_oud, ''), coalesce(r.plaat_buitenland, ''), coalesce(r.vin, ''), coalesce(r.merk, ''),
    coalesce(r.model, ''), coalesce(r.categorie, ''), coalesce(r.brandstof, ''), r.bouwjaar, r.eerste_inschrijving,
    (select id from kern.firma f where f.code = r.firma), coalesce(r.land, 'België'), coalesce(r.status, 'in gebruik'),
    coalesce(r.bestuurder, ''), r.keuring_tot, r.tankinhoud_l, coalesce(r.dropbox_map, ''),
    r.status not in ('verkocht', 'geschrapt'), 'De Wagenparkwacht'
from r
on conflict (plaat) do update set
{chr(10).join(f"  {k} = case when '{k}' = any(v.handmatig) then v.{k} else excluded.{k} end," for k in VELDEN)}
  bijgewerkt_op = now(), bijgewerkt_door = 'De Wagenparkwacht';

with r as (select * from jsonb_to_recordset({_blok(diensten)}) as x(plaat text, datum date, soort text, status text, leverancier text, km int,
    bedrag numeric, munt text, factuurnummer text, factuur_pad text, werken jsonb, omschrijving text, bron text, sleutel text))
insert into vermogen.voertuig_dienst as d (voertuig_id, datum, soort, status, leverancier, km, bedrag, munt, factuurnummer, factuur_pad,
    werken, omschrijving, bron, sleutel, bijgewerkt_door)
select v.id, r.datum, r.soort, r.status, coalesce(r.leverancier, ''), r.km, r.bedrag, coalesce(r.munt, 'EUR'), coalesce(r.factuurnummer, ''),
    coalesce(r.factuur_pad, ''), coalesce(r.werken, '[]'::jsonb), coalesce(r.omschrijving, ''), r.bron, r.sleutel, 'De Wagenparkwacht'
from r join vermogen.voertuig v on v.plaat = r.plaat
on conflict (sleutel) do update set datum = excluded.datum, soort = excluded.soort, status = excluded.status,
    leverancier = excluded.leverancier, km = excluded.km, bedrag = excluded.bedrag, munt = excluded.munt,
    factuurnummer = excluded.factuurnummer, factuur_pad = excluded.factuur_pad, werken = excluded.werken,
    omschrijving = excluded.omschrijving, bron = excluded.bron, bijgewerkt_op = now(), bijgewerkt_door = 'De Wagenparkwacht'
  where d.bijgewerkt_door = 'De Wagenparkwacht';

with r as (select * from jsonb_to_recordset({_blok(kms)}) as x(plaat text, datum date, km int, bron text, verdacht boolean, sleutel text))
insert into vermogen.voertuig_kmstand as k (voertuig_id, datum, km, bron, verdacht, sleutel, bijgewerkt_door)
select v.id, r.datum, r.km, r.bron, r.verdacht, r.sleutel, 'De Wagenparkwacht' from r join vermogen.voertuig v on v.plaat = r.plaat
on conflict (sleutel) do update set verdacht = excluded.verdacht, bijgewerkt_op = now()
  where k.bijgewerkt_door = 'De Wagenparkwacht';

with r as (select * from jsonb_to_recordset({_blok(bestuurders)}) as x(plaat text, naam text, van date, tot date, omschrijving text, sleutel text))
insert into vermogen.voertuig_bestuurder as b (voertuig_id, naam, van, tot, omschrijving, bron, sleutel, bijgewerkt_door)
select v.id, r.naam, r.van, r.tot, coalesce(r.omschrijving, ''), 'agent', r.sleutel, 'De Wagenparkwacht'
from r join vermogen.voertuig v on v.plaat = r.plaat
on conflict (sleutel) do update set tot = excluded.tot, bijgewerkt_op = now() where b.bijgewerkt_door = 'De Wagenparkwacht';

with r as (select * from jsonb_to_recordset({_blok(activiteiten)}) as x(plaat text, soort text, titel text, vervaldatum date, sleutel text))
insert into vermogen.voertuig_activiteit as a (voertuig_id, soort, titel, vervaldatum, bron, sleutel, aangemaakt_door, bijgewerkt_door)
select v.id, r.soort, r.titel, r.vervaldatum, 'agent', r.sleutel, 'De Wagenparkwacht', 'De Wagenparkwacht'
from r join vermogen.voertuig v on v.plaat = r.plaat
on conflict (sleutel) do update set titel = excluded.titel, vervaldatum = excluded.vervaldatum, bijgewerkt_op = now()
  where a.status = 'open';

-- Een signaal dat de agent niet meer ziet, is opgelost: hij sluit het zelf (een mens hoeft niets af te vinken).
update vermogen.voertuig_activiteit set status = 'gedaan', afgehandeld_op = now(), afgehandeld_door = 'De Wagenparkwacht (opgelost)',
    bijgewerkt_op = now(), bijgewerkt_door = 'De Wagenparkwacht'
where bron = 'agent' and status = 'open'
  and sleutel not in (select x ->> 'sleutel' from jsonb_array_elements({_blok(activiteiten)}) x);

-- Contracten: een autoverzekering en een autolening hangen aan hun wagen (object of omschrijving bevat de plaat).
update vermogen.verzekering z set voertuig_id = v.id from vermogen.voertuig v
where z.voertuig_id is null and lower(z.soort) = 'auto'
  and regexp_replace(upper(coalesce(z.object, '')), '[^A-Z0-9]', '', 'g') like '%' || upper(v.plaat) || '%';
update vermogen.lening l set voertuig_id = v.id from vermogen.voertuig v
where l.voertuig_id is null and regexp_replace(upper(coalesce(l.omschrijving, '')), '[^A-Z0-9]', '', 'g') like '%' || upper(v.plaat) || '%';
commit;
select json_build_object('voertuigen', (select count(*) from vermogen.voertuig), 'diensten', (select count(*) from vermogen.voertuig_dienst),
  'kmstanden', (select count(*) from vermogen.voertuig_kmstand), 'bestuurders', (select count(*) from vermogen.voertuig_bestuurder),
  'open_activiteiten', (select count(*) from vermogen.voertuig_activiteit where status = 'open'),
  'verzekeringen_gekoppeld', (select count(*) from vermogen.verzekering where voertuig_id is not null),
  'leningen_gekoppeld', (select count(*) from vermogen.lening where voertuig_id is not null));
"""
    uit = _psql(sql).strip().splitlines()
    return json.loads(uit[-1]) if uit else {}


def leasings(register):
    """Eenmalig: een lopende of afgeloste financiering uit het register als rij in vermogen.lening, als er voor die wagen
    en verstrekker nog geen staat. Daarna is de rij van de mens (de agent werkt ze nooit bij)."""
    rijen = []
    for v in register["voertuigen"]:
        l = v.get("leasing") or {}
        if not l.get("maatschappij") or not l.get("soort") or "geen" in str(l.get("soort")):
            continue
        datums = re.findall(r"\d{4}-\d{2}-\d{2}", str(l.get("einde_tekst") or l.get("einde") or ""))
        start = re.findall(r"\d{4}-\d{2}-\d{2}", str(l.get("start") or ""))
        rijen.append({"plaat": v["plaat"], "soort": "Lening" if "lening" in str(l.get("soort")).lower() else "Leasing",
                      "verstrekker": str(l["maatschappij"])[:200], "firma": v.get("firma") or "",
                      "maand": _getal(re.search(r"([\d.,]+)\s*incl", str(l.get("maandbedrag") or "")).group(1)) if re.search(r"([\d.,]+)\s*incl", str(l.get("maandbedrag") or "")) else _getal(l.get("maandbedrag")),
                      "start": start[0] if start else None, "einde": max(datums) if datums else None, "lopend": bool(l.get("lopend")),
                      "omschrijving": f"{v['plaat']} {v.get('merk_model') or ''}: {l.get('soort')}, contract {l.get('contract') or '?'}, "
                                      f"betaaldag {l.get('betaaldag') or '?'}, aankoopoptie {l.get('aankoopoptie') or '?'}. Overgenomen door De Wagenparkwacht."})
    if not rijen:
        return 0
    sql = f"""
begin;
select set_config('app.gebruiker', 'De Wagenparkwacht', true);
with r as (select * from jsonb_to_recordset({_blok(rijen)}) as x(plaat text, soort text, verstrekker text, firma text, maand numeric,
    start date, einde date, lopend boolean, omschrijving text))
insert into vermogen.lening (soort, verstrekker, firma_id, maandaflossing, startdatum, einddatum, omschrijving, voertuig_id, actief, bijgewerkt_door)
select r.soort, r.verstrekker, (select id from kern.firma f where f.code = r.firma), r.maand, r.start, r.einde, r.omschrijving, v.id, r.lopend,
    'De Wagenparkwacht'
from r join vermogen.voertuig v on v.plaat = r.plaat
where not exists (select 1 from vermogen.lening l where l.voertuig_id = v.id and l.verstrekker = r.verstrekker);
commit;
select count(*) from vermogen.lening where voertuig_id is not null;
"""
    return int((_psql(sql).strip().splitlines() or ["0"])[-1])
