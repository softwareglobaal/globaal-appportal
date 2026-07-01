'use strict';

/**
 * Eenmalige import vanuit het telefoonregister (JSON op stdin).
 *
 * Bron-JSON maken + importeren (op de VM, vanuit ~/appportal):
 *
 *   docker compose exec -T app-telefoonregister node -e "
 *     const db = require('better-sqlite3')('/app/data/telefoonregister.sqlite', { readonly: true });
 *     console.log(JSON.stringify({
 *       numbers: db.prepare('SELECT * FROM numbers').all(),
 *       secrets: db.prepare('SELECT * FROM secrets').all(),
 *       lists:   db.prepare('SELECT * FROM lists').all(),
 *     }));
 *   " | docker compose exec -T app-communicatie node scripts/import.js
 *
 * Mapping (DEFINITIEBOEK): function→doel, provider→kern.leverancier (upsert),
 * company→factuur_firma (naam-match op kern.firma, twijfel = leeg),
 * persoon_id→verantwoordelijke + gebruiker. Vrije tekst assigned_to/users
 * vervalt bewust — dat is nu curatiewerk in de nieuwe UI.
 * Idempotent: bestaande ids worden overgeslagen.
 */
const knex = require('../src/db');

function normNaam(s) {
  return String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
}

async function main() {
  const raw = await new Promise((resolve, reject) => {
    let buf = '';
    process.stdin.on('data', (c) => (buf += c));
    process.stdin.on('end', () => resolve(buf));
    process.stdin.on('error', reject);
  });
  const { numbers = [], secrets = [], lists = [] } = JSON.parse(raw);
  console.log(`bron: ${numbers.length} nummers, ${secrets.length} geheimen, ${lists.length} lijstwaarden`);

  // --- kern-referenties ophalen -------------------------------------------
  const firmas = await knex('kern.firma').select('id', 'naam');
  const firmaOpNaam = new Map(firmas.map((f) => [normNaam(f.naam), f.id]));
  const personen = new Set(
    (await knex('kern.persoon').select('id')).map((p) => p.id)
  );

  // --- leveranciers: unieke providers upserten -----------------------------
  const provisie = [...new Set(
    numbers.map((n) => String(n.provider || '').trim()).filter(Boolean)
  )];
  for (const naam of provisie) {
    const bestaat = await knex('kern.leverancier')
      .whereRaw('lower(naam) = lower(?)', [naam]).first();
    if (!bestaat) {
      await knex('kern.leverancier').insert({ naam });
    }
  }
  const leveranciers = await knex('kern.leverancier').select('id', 'naam');
  const levOpNaam = new Map(leveranciers.map((l) => [normNaam(l.naam), l.id]));
  console.log(`leveranciers: ${provisie.length} uit bron, ${leveranciers.length} totaal in kern`);

  // --- app-eigen lijsten: Land / Platform / Type ----------------------------
  const LIJST_CATS = new Set(['Land', 'Platform', 'Type']);
  let lijstNieuw = 0;
  for (const l of lists) {
    if (!LIJST_CATS.has(l.category)) continue;
    const bestaat = await knex('lijst')
      .where({ categorie: l.category, waarde: l.value }).first();
    if (!bestaat) {
      await knex('lijst').insert({
        categorie: l.category, waarde: l.value, sort_order: l.sort_order || 0,
      });
      lijstNieuw++;
    }
  }
  console.log(`lijstwaarden (Land/Platform/Type): ${lijstNieuw} nieuw`);

  // --- nummers ---------------------------------------------------------------
  let nieuw = 0, overgeslagen = 0, metVerantwoordelijke = 0, metFirma = 0;
  for (const n of numbers) {
    const bestaat = await knex('nummer').where({ id: n.id }).first();
    if (bestaat) { overgeslagen++; continue; }

    const firmaId = firmaOpNaam.get(normNaam(n.company)) || null;
    const levId = levOpNaam.get(normNaam(n.provider)) || null;
    const persoonId = n.persoon_id && personen.has(n.persoon_id) ? n.persoon_id : null;
    if (firmaId) metFirma++;
    if (persoonId) metVerantwoordelijke++;

    await knex('nummer').insert({
      id: n.id, // zelfde uuid: geheimen en bestaande links blijven kloppen
      telefoonnummer: n.phone || '',
      genormaliseerd: n.phone_normalized || '',
      status: ['Actief', 'Niet-actief', 'Onbekend'].includes(n.status) ? n.status : 'Onbekend',
      doel: n.function || '',
      land: n.country || '',
      platform: n.platform || '',
      type: n.type || '',
      omschrijving: n.description || '',
      aandacht: n.attention || '',
      leverancier_id: levId,
      factuur_firma_id: firmaId,
      verantwoordelijke_persoon_id: persoonId,
      bijgewerkt_door: 'import-telefoonregister',
    });
    if (persoonId) {
      await knex('nummer_gebruiker')
        .insert({ nummer_id: n.id, persoon_id: persoonId })
        .onConflict(['nummer_id', 'persoon_id']).ignore();
    }
    nieuw++;
  }
  console.log(`nummers: ${nieuw} geimporteerd, ${overgeslagen} bestonden al`);
  console.log(`  waarvan met factuur-firma: ${metFirma}, met verantwoordelijke: ${metVerantwoordelijke}`);

  // --- geheimen ---------------------------------------------------------------
  let geheimNieuw = 0;
  for (const s of secrets) {
    if (!s.number_id) continue;
    const nummerBestaat = await knex('nummer').where({ id: s.number_id }).first();
    if (!nummerBestaat) continue;
    const bestaat = await knex('geheim').where({ nummer_id: s.number_id }).first();
    if (bestaat) continue;
    await knex('geheim').insert({
      id: s.id,
      nummer_id: s.number_id,
      kaartnummer: s.card_number || '',
      pin1: s.pin1 || '', puk1: s.puk1 || '',
      pin2: s.pin2 || '', puk2: s.puk2 || '',
      notitie: s.note || '',
    });
    geheimNieuw++;
  }
  console.log(`geheimen: ${geheimNieuw} geimporteerd`);
  console.log('IMPORT KLAAR');
}

main()
  .then(() => process.exit(0))
  .catch((e) => { console.error('IMPORT MISLUKT:', e); process.exit(1); });
