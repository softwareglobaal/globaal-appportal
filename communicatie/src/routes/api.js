'use strict';

const express = require('express');
const knex = require('../db');
const { newId, normalizePhone, detectCountry } = require('../util');
const { broadcast, addClient } = require('../events');

const router = express.Router();

// ---- Schrijfbeveiliging ---------------------------------------------------
// Lezen mag iedereen die door de proxy binnen is; schrijven (POST/PUT/PATCH/
// DELETE) enkel wie in een editors-groep zit (zie src/auth.js, EDITOR_GROUPS).
const WRITE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
router.use((req, res, next) => {
  if (WRITE_METHODS.has(req.method) && !req.isEditor) {
    return res
      .status(403)
      .json({ error: 'Je hebt alleen-lezen toegang — wijzigen mag niet.' });
  }
  next();
});

const STATUSES = ['Actief', 'Niet-actief', 'Onbekend'];

// Tekstvelden van een nummer (vrije invoer).
const NUMMER_TEKST = ['telefoonnummer', 'doel', 'status', 'land', 'platform',
  'type', 'omschrijving', 'aandacht'];
// Verwijzingen (dropdowns uit kern) — uuid of null.
const NUMMER_REFS = ['leverancier_id', 'factuur_firma_id', 'doorfactuur_firma_id',
  'afdeling_id', 'verantwoordelijke_persoon_id'];

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const uuidOrNull = (v) => (typeof v === 'string' && UUID_RE.test(v) ? v : null);

function pickTekst(body, fields) {
  const out = {};
  for (const f of fields) {
    if (body[f] !== undefined) out[f] = body[f] === null ? '' : String(body[f]);
  }
  return out;
}

function pickRefs(body, fields) {
  const out = {};
  for (const f of fields) {
    if (body[f] !== undefined) out[f] = uuidOrNull(body[f]);
  }
  return out;
}

// FK-fout van Postgres → nette 400 i.p.v. kale 500.
function fkFout(e, res) {
  if (e && e.code === '23503') {
    res.status(400).json({ error: 'Ongeldige verwijzing (bestaat niet in de centrale lijsten).' });
    return true;
  }
  return false;
}

// Display-naam in Zoom-formaat: Voornaam (Afdeling) — vereist join kern.afdeling as pa.
const persoonNaam = "concat(p.voornaam, ' (', coalesce(pa.naam, ''), ')')";

// ---- Wie ben ik (uit Authentik-proxy) -------------------------------------
router.get('/me', (req, res) => {
  res.json({ username: req.user, groups: req.groups, isEditor: req.isEditor });
});

// ---- Live sync (SSE) ------------------------------------------------------
router.get('/events', (req, res) => {
  res.set({
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
  res.flushHeaders?.();
  res.write(`data: ${JSON.stringify({ type: 'hello' })}\n\n`);
  addClient(res);
});

// ---- Centrale referentielijsten (kern) — voor alle dropdowns ---------------
router.get('/refs', async (req, res, next) => {
  try {
    const [personen, firmas, afdelingen, leveranciers, lijstRows] = await Promise.all([
      knex('kern.persoon as p').where('p.in_dienst', true)
        .leftJoin('kern.afdeling as pa', 'pa.id', 'p.afdeling_id')
        .select('p.id', knex.raw(`${persoonNaam} as naam`)).orderBy('naam'),
      knex('kern.firma').where({ actief: true })
        .select('id', 'naam', 'code').orderBy('naam'),
      knex('kern.afdeling').where({ actief: true })
        .select('id', 'naam').orderBy('naam'),
      knex('kern.leverancier').select('id', 'naam', 'actief').orderBy('naam'),
      knex('lijst').orderBy(['categorie', 'sort_order', 'waarde']),
    ]);
    const lijsten = {};
    for (const r of lijstRows) {
      (lijsten[r.categorie] ||= []).push({ id: r.id, waarde: r.waarde, sort_order: r.sort_order });
    }
    res.json({ personen, firmas, afdelingen, leveranciers, lijsten });
  } catch (e) {
    next(e);
  }
});

// ---- Leveranciers (centrale lijst kern.leverancier; beheer hier) -----------
router.post('/leveranciers', async (req, res, next) => {
  try {
    const naam = String(req.body.naam || '').trim();
    if (!naam) return res.status(400).json({ error: 'Naam is verplicht.' });
    const exists = await knex('kern.leverancier').whereRaw('lower(naam) = lower(?)', [naam]).first();
    if (exists) return res.status(409).json({ error: 'Die leverancier bestaat al.' });
    const row = { id: newId(), naam, actief: true };
    await knex('kern.leverancier').insert(row);
    broadcast('refs');
    res.status(201).json(row);
  } catch (e) {
    next(e);
  }
});

router.put('/leveranciers/:id', async (req, res, next) => {
  try {
    const cur = await knex('kern.leverancier').where({ id: req.params.id }).first();
    if (!cur) return res.status(404).json({ error: 'Niet gevonden.' });
    const patch = {};
    if (req.body.naam !== undefined) {
      const naam = String(req.body.naam || '').trim();
      if (!naam) return res.status(400).json({ error: 'Naam is verplicht.' });
      patch.naam = naam;
    }
    if (req.body.actief !== undefined) patch.actief = Boolean(req.body.actief);
    await knex('kern.leverancier').where({ id: cur.id }).update(patch);
    broadcast('refs');
    res.json({ ...cur, ...patch });
  } catch (e) {
    next(e);
  }
});

// ---- App-eigen keuzewaarden (Land / Platform / Type) ------------------------
router.get('/lists', async (req, res, next) => {
  try {
    const rows = await knex('lijst').orderBy(['categorie', 'sort_order', 'waarde']);
    const grouped = {};
    for (const r of rows) {
      (grouped[r.categorie] ||= []).push({ id: r.id, value: r.waarde, sort_order: r.sort_order });
    }
    res.json(grouped);
  } catch (e) {
    next(e);
  }
});

router.post('/lists', async (req, res, next) => {
  try {
    const categorie = String(req.body.category || req.body.categorie || '').trim();
    const waarde = String(req.body.value || req.body.waarde || '').trim();
    if (!categorie || !waarde) return res.status(400).json({ error: 'Categorie en waarde zijn verplicht.' });
    const exists = await knex('lijst').where({ categorie, waarde }).first();
    if (exists) return res.status(409).json({ error: 'Die waarde bestaat al in deze lijst.' });
    const max = await knex('lijst').where({ categorie }).max({ m: 'sort_order' }).first();
    const row = { id: newId(), categorie, waarde, sort_order: (Number(max.m) || 0) + 1 };
    await knex('lijst').insert(row);
    broadcast('lists');
    res.status(201).json(row);
  } catch (e) {
    next(e);
  }
});

router.put('/lists/:id', async (req, res, next) => {
  try {
    const waarde = String(req.body.value || req.body.waarde || '').trim();
    if (!waarde) return res.status(400).json({ error: 'Waarde is verplicht.' });
    const cur = await knex('lijst').where({ id: req.params.id }).first();
    if (!cur) return res.status(404).json({ error: 'Niet gevonden.' });
    const patch = { waarde };
    if (req.body.sort_order !== undefined) patch.sort_order = Number(req.body.sort_order) || 0;
    await knex('lijst').where({ id: req.params.id }).update(patch);
    broadcast('lists');
    res.json({ ...cur, ...patch });
  } catch (e) {
    next(e);
  }
});

router.delete('/lists/:id', async (req, res, next) => {
  try {
    await knex('lijst').where({ id: req.params.id }).del();
    broadcast('lists');
    res.json({ ok: true });
  } catch (e) {
    next(e);
  }
});

// ---- Dubbelcheck ----------------------------------------------------------
router.get('/numbers/check', async (req, res, next) => {
  try {
    const norm = normalizePhone(req.query.phone || '');
    const excludeId = req.query.exclude || null;
    if (!norm) return res.json({ duplicate: false });
    let q = knex('nummer').where({ genormaliseerd: norm });
    if (excludeId) q = q.andWhereNot({ id: excludeId });
    const rows = await q.select('id', 'telefoonnummer', 'doel', 'status');
    res.json({ duplicate: rows.length > 0, matches: rows, country: detectCountry(req.query.phone) });
  } catch (e) {
    next(e);
  }
});

// Set van genormaliseerde nummers die méér dan één keer voorkomen.
async function duplicateNormSet() {
  const rows = await knex('nummer')
    .whereNot({ genormaliseerd: '' })
    .groupBy('genormaliseerd')
    .havingRaw('COUNT(*) > 1')
    .select('genormaliseerd');
  return new Set(rows.map((r) => r.genormaliseerd));
}

// ---- Statistieken (KPI-kaarten) -------------------------------------------
router.get('/stats', async (req, res, next) => {
  try {
    const dupSet = await duplicateNormSet();
    const all = await knex('nummer').select('status', 'aandacht', 'genormaliseerd');
    const stats = { total: all.length, actief: 0, niet_actief: 0, onbekend: 0, dubbel: 0, probleem: 0 };
    for (const r of all) {
      if (r.status === 'Actief') stats.actief++;
      else if (r.status === 'Niet-actief') stats.niet_actief++;
      else if (r.status === 'Onbekend') stats.onbekend++;
      const dup = r.genormaliseerd && dupSet.has(r.genormaliseerd);
      if (dup) stats.dubbel++;
      if (dup || (r.aandacht || '').trim()) stats.probleem++;
    }
    res.json(stats);
  } catch (e) {
    next(e);
  }
});

// ---- Nummers ----------------------------------------------------------------
function nummerQuery() {
  return knex('nummer as n')
    .leftJoin('kern.persoon as p', 'p.id', 'n.verantwoordelijke_persoon_id')
    .leftJoin('kern.afdeling as pa', 'pa.id', 'p.afdeling_id')
    .leftJoin('kern.firma as ff', 'ff.id', 'n.factuur_firma_id')
    .leftJoin('kern.firma as df', 'df.id', 'n.doorfactuur_firma_id')
    .leftJoin('kern.leverancier as lev', 'lev.id', 'n.leverancier_id')
    .leftJoin('kern.afdeling as afd', 'afd.id', 'n.afdeling_id')
    .select(
      'n.*',
      knex.raw(`${persoonNaam} as verantwoordelijke_naam`),
      'ff.naam as factuur_firma_naam', 'ff.code as factuur_firma_code',
      'df.naam as doorfactuur_firma_naam', 'df.code as doorfactuur_firma_code',
      'lev.naam as leverancier_naam',
      'afd.naam as afdeling_naam'
    );
}

// Gebruikers (multi) per nummer, in één query voor een set nummer-ids.
async function gebruikersVoor(ids) {
  if (!ids.length) return {};
  const rows = await knex('nummer_gebruiker as ng')
    .join('kern.persoon as p', 'p.id', 'ng.persoon_id')
    .leftJoin('kern.afdeling as pa', 'pa.id', 'p.afdeling_id')
    .whereIn('ng.nummer_id', ids)
    .select('ng.nummer_id', 'ng.persoon_id', 'ng.volgorde', knex.raw(`${persoonNaam} as naam`))
    .orderBy([{ column: 'ng.volgorde' }, { column: 'naam' }]);
  const map = {};
  for (const r of rows) {
    (map[r.nummer_id] ||= []).push({ persoon_id: r.persoon_id, naam: r.naam });
  }
  return map;
}

async function syncGebruikers(nummerId, persoonIds) {
  // Volgorde in de array = belvolgorde (queue): index 0 neemt eerst op.
  const gewenst = [...new Set((persoonIds || []).map(uuidOrNull).filter(Boolean))];
  await knex('nummer_gebruiker').where({ nummer_id: nummerId }).del();
  if (gewenst.length) {
    await knex('nummer_gebruiker').insert(
      gewenst.map((pid, i) => ({ nummer_id: nummerId, persoon_id: pid, volgorde: i + 1 }))
    );
  }
}

router.get('/numbers', async (req, res, next) => {
  try {
    const { land, status, q, firma, leverancier, afdeling, duplicates, attention } = req.query;
    let query = nummerQuery();
    if (land) query = query.where('n.land', land);
    if (status) query = query.where('n.status', status);
    if (firma) {
      const firmaIds = String(firma).split(',').filter(Boolean);
      query = query.whereIn('n.factuur_firma_id', firmaIds);
    }
    if (leverancier) query = query.where('n.leverancier_id', leverancier);
    if (afdeling) query = query.where('n.afdeling_id', afdeling);
    if (attention === '1') query = query.andWhere('n.aandacht', '<>', '');
    if (q) {
      const term = `%${String(q).toLowerCase()}%`;
      query = query.where((b) => {
        b.whereRaw('LOWER(n.telefoonnummer) LIKE ?', [term])
          .orWhereRaw('LOWER(n.doel) LIKE ?', [term])
          .orWhereRaw('LOWER(n.omschrijving) LIKE ?', [term])
          .orWhereRaw(`LOWER(${persoonNaam}) LIKE ?`, [term]);
      });
    }
    const rows = await query.orderBy([
      { column: 'n.land' }, { column: 'ff.naam' }, { column: 'n.doel' },
    ]);

    const dupSet = await duplicateNormSet();
    const gebruikers = await gebruikersVoor(rows.map((r) => r.id));
    let result = rows.map((r) => ({
      ...r,
      gebruikers: gebruikers[r.id] || [],
      is_duplicate: Boolean(r.genormaliseerd && dupSet.has(r.genormaliseerd)),
    }));
    if (duplicates === '1') result = result.filter((r) => r.is_duplicate);

    res.json(result);
  } catch (e) {
    next(e);
  }
});

router.get('/numbers/:id', async (req, res, next) => {
  try {
    const row = await nummerQuery().where('n.id', req.params.id).first();
    if (!row) return res.status(404).json({ error: 'Niet gevonden.' });
    const geheim = (await knex('geheim').where({ nummer_id: row.id }).first()) || null;
    const gebruikers = (await gebruikersVoor([row.id]))[row.id] || [];
    let is_duplicate = false;
    if (row.genormaliseerd) {
      const cnt = await knex('nummer')
        .where({ genormaliseerd: row.genormaliseerd })
        .count({ c: '*' })
        .first();
      is_duplicate = Number(cnt.c) > 1;
    }
    res.json({ ...row, geheim, gebruikers, is_duplicate });
  } catch (e) {
    next(e);
  }
});

router.post('/numbers', async (req, res, next) => {
  try {
    const data = { ...pickTekst(req.body, NUMMER_TEKST), ...pickRefs(req.body, NUMMER_REFS) };
    if (!data.telefoonnummer || !data.telefoonnummer.trim())
      return res.status(400).json({ error: 'Telefoonnummer is verplicht.' });
    if (!data.status) data.status = 'Actief';
    if (!STATUSES.includes(data.status))
      return res.status(400).json({ error: 'Ongeldige status.' });

    const norm = normalizePhone(data.telefoonnummer);
    const dup = await knex('nummer').where({ genormaliseerd: norm }).first();
    if (dup) {
      return res.status(409).json({
        error: 'Dit nummer bestaat al.',
        existing: { id: dup.id, telefoonnummer: dup.telefoonnummer, doel: dup.doel, status: dup.status },
      });
    }
    if (!data.land) data.land = detectCountry(data.telefoonnummer) || '';

    const row = {
      id: newId(),
      ...data,
      genormaliseerd: norm,
      bijgewerkt_door: req.user,
    };
    await knex('nummer').insert(row);
    await syncGebruikers(row.id, req.body.gebruiker_ids);
    broadcast('numbers', { action: 'create', id: row.id });
    res.status(201).json(row);
  } catch (e) {
    if (fkFout(e, res)) return;
    next(e);
  }
});

router.put('/numbers/:id', async (req, res, next) => {
  try {
    const cur = await knex('nummer').where({ id: req.params.id }).first();
    if (!cur) return res.status(404).json({ error: 'Niet gevonden.' });
    const data = { ...pickTekst(req.body, NUMMER_TEKST), ...pickRefs(req.body, NUMMER_REFS) };
    if (data.status && !STATUSES.includes(data.status))
      return res.status(400).json({ error: 'Ongeldige status.' });

    if (data.telefoonnummer !== undefined) {
      const norm = normalizePhone(data.telefoonnummer);
      if (norm && norm !== cur.genormaliseerd) {
        const dup = await knex('nummer')
          .where({ genormaliseerd: norm })
          .andWhereNot({ id: cur.id })
          .first();
        if (dup) {
          return res.status(409).json({
            error: 'Een ander record gebruikt dit nummer al.',
            existing: { id: dup.id, telefoonnummer: dup.telefoonnummer, doel: dup.doel },
          });
        }
      }
      data.genormaliseerd = norm;
    }
    data.bijgewerkt_door = req.user;
    data.bijgewerkt_op = knex.fn.now();
    await knex('nummer').where({ id: cur.id }).update(data);
    if (req.body.gebruiker_ids !== undefined) {
      await syncGebruikers(cur.id, req.body.gebruiker_ids);
    }
    const updated = await knex('nummer').where({ id: cur.id }).first();
    broadcast('numbers', { action: 'update', id: cur.id });
    res.json(updated);
  } catch (e) {
    if (fkFout(e, res)) return;
    next(e);
  }
});

router.patch('/numbers/:id/status', async (req, res, next) => {
  try {
    const status = String(req.body.status || '').trim();
    if (!STATUSES.includes(status))
      return res.status(400).json({ error: 'Ongeldige status.' });
    const cur = await knex('nummer').where({ id: req.params.id }).first();
    if (!cur) return res.status(404).json({ error: 'Niet gevonden.' });
    await knex('nummer')
      .where({ id: cur.id })
      .update({ status, bijgewerkt_door: req.user, bijgewerkt_op: knex.fn.now() });
    broadcast('numbers', { action: 'status', id: cur.id });
    res.json({ id: cur.id, status });
  } catch (e) {
    next(e);
  }
});

router.post('/numbers/:id/clear-attention', async (req, res, next) => {
  try {
    const cur = await knex('nummer').where({ id: req.params.id }).first();
    if (!cur) return res.status(404).json({ error: 'Niet gevonden.' });
    await knex('nummer')
      .where({ id: cur.id })
      .update({ aandacht: '', bijgewerkt_door: req.user, bijgewerkt_op: knex.fn.now() });
    broadcast('numbers', { action: 'update', id: cur.id });
    res.json({ ok: true });
  } catch (e) {
    next(e);
  }
});

router.delete('/numbers/:id', async (req, res, next) => {
  try {
    const cur = await knex('nummer').where({ id: req.params.id }).first();
    if (!cur) return res.status(404).json({ error: 'Niet gevonden.' });
    await knex('nummer').where({ id: cur.id }).del(); // geheim + gebruikers casc.
    broadcast('numbers', { action: 'delete', id: cur.id });
    res.json({ ok: true });
  } catch (e) {
    next(e);
  }
});

// ---- Afgeschermde inloggegevens ------------------------------------------
const GEHEIM_FIELDS = ['kaartnummer', 'pin1', 'puk1', 'pin2', 'puk2', 'notitie'];

router.put('/numbers/:id/secret', async (req, res, next) => {
  try {
    const num = await knex('nummer').where({ id: req.params.id }).first();
    if (!num) return res.status(404).json({ error: 'Nummer niet gevonden.' });
    const data = pickTekst(req.body, GEHEIM_FIELDS);
    const existing = await knex('geheim').where({ nummer_id: num.id }).first();
    if (existing) {
      await knex('geheim')
        .where({ id: existing.id })
        .update({ ...data, bijgewerkt_op: knex.fn.now() });
    } else {
      await knex('geheim').insert({
        id: newId(),
        nummer_id: num.id,
        kaartnummer: '', pin1: '', puk1: '', pin2: '', puk2: '', notitie: '',
        ...data,
      });
    }
    broadcast('numbers', { action: 'secret', id: num.id });
    const geheim = await knex('geheim').where({ nummer_id: num.id }).first();
    res.json(geheim);
  } catch (e) {
    next(e);
  }
});

// ---- E-mailadressen (tab 2) -------------------------------------------------
const EMAIL_TEKST = ['omschrijving'];
const EMAIL_REFS = ['firma_id', 'verantwoordelijke_persoon_id'];

function emailQuery() {
  return knex('emailadres as e')
    .leftJoin('kern.firma as f', 'f.id', 'e.firma_id')
    .leftJoin('kern.persoon as p', 'p.id', 'e.verantwoordelijke_persoon_id')
    .leftJoin('kern.afdeling as pa', 'pa.id', 'p.afdeling_id')
    .select('e.*', 'f.naam as firma_naam', 'f.code as firma_code',
      knex.raw(`${persoonNaam} as verantwoordelijke_naam`));
}

router.get('/emails', async (req, res, next) => {
  try {
    const { q, firma, open } = req.query;
    let query = emailQuery();
    if (firma) query = query.where('e.firma_id', firma);
    if (open === '1') query = query.whereNull('e.verantwoordelijke_persoon_id');
    if (q) {
      const term = `%${String(q).toLowerCase()}%`;
      query = query.where((b) => {
        b.whereRaw('LOWER(e.adres::text) LIKE ?', [term])
          .orWhereRaw('LOWER(e.omschrijving) LIKE ?', [term])
          .orWhereRaw(`LOWER(${persoonNaam}) LIKE ?`, [term])
          .orWhereRaw('LOWER(f.naam) LIKE ?', [term]);
      });
    }
    const rows = await query.orderBy([{ column: 'f.naam' }, { column: 'e.adres' }]);
    res.json(rows);
  } catch (e) {
    next(e);
  }
});

router.post('/emails', async (req, res, next) => {
  try {
    const adres = String(req.body.adres || '').trim();
    if (!adres || !adres.includes('@'))
      return res.status(400).json({ error: 'Een geldig e-mailadres is verplicht.' });
    const exists = await knex('emailadres').where({ adres }).first();
    if (exists) return res.status(409).json({ error: 'Dit adres bestaat al.' });
    const row = {
      id: newId(),
      adres,
      ...pickTekst(req.body, EMAIL_TEKST),
      ...pickRefs(req.body, EMAIL_REFS),
      actief: req.body.actief === undefined ? true : Boolean(req.body.actief),
      bijgewerkt_door: req.user,
    };
    await knex('emailadres').insert(row);
    broadcast('emails', { action: 'create', id: row.id });
    res.status(201).json(row);
  } catch (e) {
    if (fkFout(e, res)) return;
    next(e);
  }
});

router.put('/emails/:id', async (req, res, next) => {
  try {
    const cur = await knex('emailadres').where({ id: req.params.id }).first();
    if (!cur) return res.status(404).json({ error: 'Niet gevonden.' });
    const patch = { ...pickTekst(req.body, EMAIL_TEKST), ...pickRefs(req.body, EMAIL_REFS) };
    if (req.body.adres !== undefined) {
      const adres = String(req.body.adres || '').trim();
      if (!adres || !adres.includes('@'))
        return res.status(400).json({ error: 'Een geldig e-mailadres is verplicht.' });
      const dup = await knex('emailadres').where({ adres }).andWhereNot({ id: cur.id }).first();
      if (dup) return res.status(409).json({ error: 'Een ander record gebruikt dit adres al.' });
      patch.adres = adres;
    }
    if (req.body.actief !== undefined) patch.actief = Boolean(req.body.actief);
    patch.bijgewerkt_door = req.user;
    patch.bijgewerkt_op = knex.fn.now();
    await knex('emailadres').where({ id: cur.id }).update(patch);
    const updated = await knex('emailadres').where({ id: cur.id }).first();
    broadcast('emails', { action: 'update', id: cur.id });
    res.json(updated);
  } catch (e) {
    if (fkFout(e, res)) return;
    next(e);
  }
});

router.delete('/emails/:id', async (req, res, next) => {
  try {
    await knex('emailadres').where({ id: req.params.id }).del();
    broadcast('emails', { action: 'delete', id: req.params.id });
    res.json({ ok: true });
  } catch (e) {
    next(e);
  }
});

module.exports = router;
