'use strict';

// Databaseconfiguratie: PostgreSQL, schema `communicatie` in de appportal-database.
// Het schema zelf wordt beheerd via db/migrations/ in de stack-repo (geen
// knex-migraties hier); deze app leest kern.* en schrijft communicatie.*
// met de rol `communicatie` (zie db/roles.sql).

module.exports = {
  client: 'pg',
  connection:
    process.env.DATABASE_URL ||
    'postgres://communicatie:communicatie@localhost:5432/appportal',
  searchPath: ['communicatie', 'public'],
  pool: { min: 2, max: 10 },
};
