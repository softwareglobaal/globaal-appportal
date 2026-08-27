-- 135: platform-inhoud van angela.sr in de database.
-- De pagina's Verhalen, Jobs, De Spiegel, Sterk en zwak en de lopende band op
-- de home stonden als Python-lijsten in de app (angela-site/app/platform_paginas.py).
-- Angela beheert die inhoud voortaan zelf via Claude (MCP-endpoint op
-- https://angela.sr/mcp); daarvoor moet de inhoud in de database staan.
-- De app zaait de tabel eenmalig met de bestaande voorbeeldinhoud zodra hij
-- start en de tabel leeg is (advisory lock tegen dubbele seed).
-- Rechten: de default privileges uit 079 dekken nieuwe tabellen in dit schema
-- (items_writer lezen/schrijven, portal lezen).

CREATE TABLE IF NOT EXISTS items.platform_inhoud (
    id             bigserial PRIMARY KEY,
    soort          text NOT NULL
                    CHECK (soort IN ('verhaal','job','column','woord',
                                     'spiegel_ook','sterk','zwak','band')),
    -- De inhoud zelf, zelfde sleutels als de oude Python-dicts per soort
    -- (validatie in de app: mcp_server.py toetst tegen platform_paginas.SOORTEN).
    velden         jsonb NOT NULL DEFAULT '{}'::jsonb,
    volgorde       integer NOT NULL DEFAULT 0,
    actief         boolean NOT NULL DEFAULT true,
    door           text,
    aangemaakt_op  timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_op  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_items_platform_inhoud
    ON items.platform_inhoud (soort, actief, volgorde);
