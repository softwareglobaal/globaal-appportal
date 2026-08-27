-- 137: Blog Elevait (zelf schrijven op het interne dashboard)
-- Aanleiding: besluit Shaniel 26-08-2026. Blogs voor zichtbaarheid en SEO,
-- geschreven door de partners zonder git of markdown-bestanden aan te raken:
-- een editor op intern.elevaitnv.com schrijft naar deze tabel, de publieke
-- site leest de gepubliceerde artikelen (fase 2). Een concept blijft intern
-- tot iemand het bewust publiceert.

CREATE TABLE IF NOT EXISTS elevait.blog (
    id              bigserial PRIMARY KEY,
    slug            text NOT NULL UNIQUE,          -- de URL: /blog/<slug>
    titel           text NOT NULL DEFAULT '',
    beschrijving    text NOT NULL DEFAULT '',      -- meta-description + intro
    inhoud          text NOT NULL DEFAULT '',      -- markdown
    tags            jsonb NOT NULL DEFAULT '[]'::jsonb,
    status          text NOT NULL DEFAULT 'concept'
                    CHECK (status IN ('concept', 'gepubliceerd')),
    auteur          text NOT NULL DEFAULT 'Team Elevait',
    door            text NOT NULL DEFAULT '',      -- gebruiker die het aanmaakte
    gepubliceerd_op timestamptz,
    aangemaakt_op   timestamptz NOT NULL DEFAULT now(),
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now()
);
-- De publieke lijst: gepubliceerd, nieuwste eerst.
CREATE INDEX IF NOT EXISTS ix_elevait_blog_publiek
    ON elevait.blog (gepubliceerd_op DESC) WHERE status = 'gepubliceerd';

-- De publieke site mag straks de gepubliceerde blogs lezen (fase 2). Alleen
-- SELECT; de portal-graaf heeft niets aan blogs, dus die niet.
REVOKE SELECT ON elevait.blog FROM portal;

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('blog', 'Blog',
   'Een artikel voor de Elevait-website, geschreven op het interne dashboard zonder git of bestanden aan te raken. Een concept blijft intern tot iemand het publiceert; de publieke site toont alleen gepubliceerde artikelen. Bedoeld voor zichtbaarheid en SEO rond het thema AI en Suriname.')
ON CONFLICT (sleutel) DO NOTHING;
