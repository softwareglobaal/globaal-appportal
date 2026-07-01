'use strict';

/**
 * Authenticatie gebeurt VOOR deze app, door de reverse proxy (Authentik,
 * forward-auth). Wij bouwen geen eigen loginscherm — we lezen alleen de
 * ingelogde gebruiker (en zijn groepen) uit de proxy-headers.
 *
 * Iedereen die binnen is, mag LEZEN. SCHRIJVEN (toevoegen/wijzigen/verwijderen)
 * mag enkel wie in een editors-groep zit. Welke groepen dat zijn, staat in de
 * env-variabele EDITOR_GROUPS (komma-gescheiden); standaard
 * "communicatie-editors,admin".
 *
 * Lokaal (zonder proxy) valt de gebruikersnaam terug op DEV_USER en mag er
 * gewoon bewerkt worden, zodat de app ook zonder Authentik te gebruiken is
 * tijdens ontwikkeling.
 */

const HEADER_CANDIDATES = [
  'x-authentik-username',
  'x-forwarded-preferred-username',
  'x-forwarded-user',
  'x-auth-request-user',
  'remote-user',
];

// Authentik stuurt de groepen door als één header, gescheiden door '|'
// (we accepteren ook ',' voor de zekerheid).
const GROUPS_HEADER = 'x-authentik-groups';

const EDITOR_GROUPS = (process.env.EDITOR_GROUPS || 'communicatie-editors,admin')
  .split(',')
  .map((s) => s.trim().toLowerCase())
  .filter(Boolean);

function currentUser(req) {
  for (const h of HEADER_CANDIDATES) {
    const v = req.headers[h];
    if (v && String(v).trim()) return String(v).trim();
  }
  return process.env.DEV_USER || 'lokaal';
}

function currentGroups(req) {
  const v = req.headers[GROUPS_HEADER];
  if (!v || !String(v).trim()) return [];
  return String(v)
    .split(/[|,]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

// Zit de gebruiker achter de proxy? Zo niet (lokaal/dev), dan mag alles.
function behindProxy(req) {
  return Boolean(req.headers['x-authentik-username'] || req.headers[GROUPS_HEADER]);
}

function isEditor(req) {
  if (!behindProxy(req)) return true; // lokale ontwikkeling
  const groups = currentGroups(req).map((g) => g.toLowerCase());
  return groups.some((g) => EDITOR_GROUPS.includes(g));
}

function attachUser(req, res, next) {
  req.user = currentUser(req);
  req.groups = currentGroups(req);
  req.isEditor = isEditor(req);
  next();
}

module.exports = { attachUser, currentUser, currentGroups, isEditor, EDITOR_GROUPS };
