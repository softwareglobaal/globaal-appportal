'use strict';

const path = require('path');
const express = require('express');
const knex = require('./src/db');
const { attachUser } = require('./src/auth');
const apiRouter = require('./src/routes/api');
const exportRouter = require('./src/routes/export');

const app = express();
const PORT = process.env.PORT || 3008;

app.disable('x-powered-by');
app.use(express.json({ limit: '1mb' }));

// Ingelogde gebruiker uit Authentik-proxy lezen (geen eigen login).
app.use(attachUser);

// API + export
app.use('/api', apiRouter);
app.use('/api', exportRouter);

// Statische frontend
app.use(express.static(path.join(__dirname, 'public')));

// Foutafhandeling (JSON)
app.use((err, req, res, next) => {
  // eslint-disable-line no-unused-vars
  console.error(err);
  res.status(500).json({ error: 'Er ging iets mis op de server.' });
});

async function start() {
  // Schema wordt beheerd via db/migrations/ in de stack-repo (scripts/db-migrate.sh);
  // hier alleen controleren dat de database bereikbaar is en het schema bestaat.
  await knex.raw('SELECT 1 FROM communicatie.nummer LIMIT 1');

  app.listen(PORT, () => {
    console.log(`Communicatie dashboard draait op http://localhost:${PORT}`);
  });
}

start().catch((e) => {
  console.error('Kon de server niet starten:', e);
  process.exit(1);
});
