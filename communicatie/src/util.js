'use strict';

const crypto = require('crypto');

function newId() {
  return crypto.randomUUID();
}

/**
 * Normaliseer een telefoonnummer voor vergelijking/dubbelcheck:
 * alle niet-cijfers weg (spaties, streepjes, plus, punten).
 * Een leidende internationale '00' of '+' wordt mee genormaliseerd door
 * eenvoudig alle cijfers te behouden — voldoende om dubbels te vangen.
 */
function normalizePhone(raw) {
  if (raw === null || raw === undefined) return '';
  return String(raw).replace(/\D+/g, '');
}

/**
 * Leid het land af uit het nummer (heuristiek, gebruiker mag overschrijven).
 *  - Belgisch: begint met '0' en ~9-10 cijfers (vaste lijn of mobiel).
 *  - Surinaams: 7 cijfers (eventueel met streepje, bv. 847-5945 / 8665369).
 * Geeft '' terug als het niet duidelijk is.
 */
function detectCountry(raw) {
  const n = normalizePhone(raw);
  if (!n) return '';
  if (n.startsWith('0') && (n.length === 9 || n.length === 10)) return 'België';
  if (n.startsWith('32') && (n.length === 11 || n.length === 12)) return 'België';
  if (n.length === 7) return 'Suriname';
  if (n.startsWith('597')) return 'Suriname';
  return '';
}

module.exports = { newId, normalizePhone, detectCountry };
