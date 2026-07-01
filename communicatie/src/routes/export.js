'use strict';

const express = require('express');
const ExcelJS = require('exceljs');
const knex = require('../db');

const router = express.Router();

const persoonNaam = "concat(p.voornaam, ' (', coalesce(pa.naam, '?'), ')')";

/**
 * Exporteer de volledige dataset naar .xlsx (tabbladen Nummers, E-mailadressen,
 * Lijsten, Geheim - Inloggegevens), zodat we nooit vastzitten aan de tool.
 */
router.get('/export', async (req, res, next) => {
  try {
    const includeSecrets = req.query.secrets !== '0';
    const wb = new ExcelJS.Workbook();
    wb.creator = 'Communicatie dashboard';
    wb.created = new Date();

    // --- Nummers ---
    const numbers = await knex('nummer as n')
      .leftJoin('kern.persoon as p', 'p.id', 'n.verantwoordelijke_persoon_id')
      .leftJoin('kern.afdeling as pa', 'pa.id', 'p.afdeling_id')
      .leftJoin('kern.firma as ff', 'ff.id', 'n.factuur_firma_id')
      .leftJoin('kern.firma as df', 'df.id', 'n.doorfactuur_firma_id')
      .leftJoin('kern.leverancier as lev', 'lev.id', 'n.leverancier_id')
      .leftJoin('kern.afdeling as afd', 'afd.id', 'n.afdeling_id')
      .select(
        'n.telefoonnummer', 'n.land', 'n.doel', 'n.status',
        knex.raw(`${persoonNaam} as verantwoordelijke`),
        'ff.naam as factuur_firma', 'df.naam as doorfactuur_firma',
        'lev.naam as leverancier', 'afd.naam as afdeling',
        'n.platform', 'n.type', 'n.omschrijving', 'n.aandacht'
      )
      .orderBy([{ column: 'n.land' }, { column: 'ff.naam' }, { column: 'n.doel' }]);
    const wsN = wb.addWorksheet('Nummers');
    wsN.columns = [
      { header: 'Telefoonnummer', key: 'telefoonnummer', width: 18 },
      { header: 'Land', key: 'land', width: 12 },
      { header: 'Doel', key: 'doel', width: 28 },
      { header: 'Status', key: 'status', width: 12 },
      { header: 'Verantwoordelijke', key: 'verantwoordelijke', width: 22 },
      { header: 'Factuur-firma', key: 'factuur_firma', width: 20 },
      { header: 'Doorfactuur-firma', key: 'doorfactuur_firma', width: 20 },
      { header: 'Leverancier', key: 'leverancier', width: 16 },
      { header: 'Afdeling', key: 'afdeling', width: 16 },
      { header: 'Platform', key: 'platform', width: 12 },
      { header: 'Type', key: 'type', width: 12 },
      { header: 'Omschrijving', key: 'omschrijving', width: 30 },
      { header: 'Aandacht', key: 'aandacht', width: 30 },
    ];
    wsN.getRow(1).font = { bold: true };
    numbers.forEach((n) => wsN.addRow(n));

    // --- E-mailadressen ---
    const emails = await knex('emailadres as e')
      .leftJoin('kern.firma as f', 'f.id', 'e.firma_id')
      .leftJoin('kern.persoon as p', 'p.id', 'e.verantwoordelijke_persoon_id')
      .leftJoin('kern.afdeling as pa', 'pa.id', 'p.afdeling_id')
      .select('e.adres', 'f.naam as firma',
        knex.raw(`${persoonNaam} as verantwoordelijke`),
        'e.omschrijving', 'e.actief')
      .orderBy([{ column: 'f.naam' }, { column: 'e.adres' }]);
    const wsE = wb.addWorksheet('E-mailadressen');
    wsE.columns = [
      { header: 'E-mailadres', key: 'adres', width: 32 },
      { header: 'Firma', key: 'firma', width: 20 },
      { header: 'Verantwoordelijke', key: 'verantwoordelijke', width: 22 },
      { header: 'Omschrijving', key: 'omschrijving', width: 30 },
      { header: 'Actief', key: 'actief', width: 10 },
    ];
    wsE.getRow(1).font = { bold: true };
    emails.forEach((e) => wsE.addRow(e));

    // --- Lijsten ---
    const lists = await knex('lijst').orderBy(['categorie', 'sort_order', 'waarde']);
    const byCat = {};
    for (const l of lists) (byCat[l.categorie] ||= []).push(l.waarde);
    const cats = Object.keys(byCat);
    const wsL = wb.addWorksheet('Lijsten');
    wsL.addRow(cats);
    wsL.getRow(1).font = { bold: true };
    const maxLen = Math.max(0, ...cats.map((c) => byCat[c].length));
    for (let i = 0; i < maxLen; i++) {
      wsL.addRow(cats.map((c) => byCat[c][i] || null));
    }
    cats.forEach((_, i) => (wsL.getColumn(i + 1).width = 18));

    // --- Geheim - Inloggegevens ---
    if (includeSecrets) {
      const secrets = await knex('geheim')
        .leftJoin('nummer', 'geheim.nummer_id', 'nummer.id')
        .select(
          'nummer.telefoonnummer as telefoonnummer',
          'geheim.notitie as notitie',
          'geheim.kaartnummer as kaartnummer',
          'geheim.pin1', 'geheim.puk1', 'geheim.pin2', 'geheim.puk2'
        );
      const wsS = wb.addWorksheet('Geheim - Inloggegevens');
      wsS.columns = [
        { header: 'Telefoonnummer', key: 'telefoonnummer', width: 18 },
        { header: 'Notitie', key: 'notitie', width: 28 },
        { header: 'Kaartnummer (SSN)', key: 'kaartnummer', width: 20 },
        { header: 'PIN 1', key: 'pin1', width: 10 },
        { header: 'PUK 1', key: 'puk1', width: 12 },
        { header: 'PIN 2', key: 'pin2', width: 10 },
        { header: 'PUK 2', key: 'puk2', width: 12 },
      ];
      wsS.getRow(1).font = { bold: true };
      secrets.forEach((s) => wsS.addRow(s));
      wsS.state = 'hidden';
    }

    const stamp = new Date().toISOString().slice(0, 10);
    res.setHeader(
      'Content-Type',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    );
    res.setHeader(
      'Content-Disposition',
      `attachment; filename="Communicatie export ${stamp}.xlsx"`
    );
    await wb.xlsx.write(res);
    res.end();
  } catch (e) {
    next(e);
  }
});

module.exports = router;
