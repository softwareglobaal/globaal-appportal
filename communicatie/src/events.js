'use strict';

/**
 * Eenvoudige live-sync via Server-Sent Events (SSE).
 * Bij elke wijziging sturen we een 'changed'-event naar alle verbonden
 * clients; die halen de data dan opnieuw op. Geen extra infrastructuur nodig.
 */

const clients = new Set();

function addClient(res) {
  clients.add(res);
  res.on('close', () => clients.delete(res));
}

function broadcast(type, payload = {}) {
  const data = JSON.stringify({ type, ...payload, at: new Date().toISOString() });
  for (const res of clients) {
    try {
      res.write(`data: ${data}\n\n`);
    } catch (_) {
      clients.delete(res);
    }
  }
}

function clientCount() {
  return clients.size;
}

module.exports = { addClient, broadcast, clientCount };
