# Angela - werkdashboard initiatief Suriname

Vangbak voor alles rond het initiatief: notities, links, bestanden, taken en
beslissingen, elk gekoppeld aan een werkstroom (merk, website, webshop, inkoop,
fiscaal, social, data). Bedoeld om snel iets neer te leggen tijdens of vlak na
een overleg, en om er daarna structuur in aan te brengen.

Draait achter de forward-auth van de portal op `angela.<BASE_DOMAIN>`. Geen
eigen login: de gebruiker komt binnen via de `X-authentik-*` headers.

## Werkstromen

Vaste indeling, aanpasbaar in `angela.werkstroom`:

| Sleutel | Werkstroom |
|---|---|
| merk | Merk en branding |
| website | Website en bio-pagina |
| webshop | Webshop |
| inkoop | Inkoop en veilingen |
| fiscaal | Fiscaal en juridisch |
| social | Social media en content |
| data | Data en netwerk |

## Omgevingsvariabelen

| Variabele | Uitleg |
|---|---|
| `PORT` | Poort waarop de app luistert. Standaard 3016. |
| `ANGELA_DB_URL` | Postgres-DSN met rol `angela_writer` (schema `angela`, leest `kern.persoon`). |
| `ANGELA_UPLOAD_DIR` | Map voor bijlagen. Standaard `/data/bijlagen`, komt van een volume. |
| `ANGELA_MAX_UPLOAD_MB` | Maximum per upload in MB. Standaard 50, moet passen bij `client_max_body_size` in nginx. |
| `ANGELA_TITEL` | Naam in de kop. Standaard `Angela`. |
| `ANGELA_ONDERTITEL` | Regel onder de naam. Standaard `Initiatief Suriname`. |
| `EDITOR_GROUPS` | Komma-lijst Authentik-groepen die mogen schrijven. Leeg = iedereen die door forward-auth komt. |
| `SECRET_KEY` | Sleutel voor flash-berichten. Zonder waarde wordt er per start een willekeurige gezet. |

## Data

Schema `angela` (migratie `db/migrations/097-angela.sql`):

- `werkstroom` - de vaste indeling
- `betrokkene` - koppelbare personenlaag, `persoon_id` verwijst naar `kern.persoon`
- `item` - alles wat gedropt wordt, met `soort`, `status`, herkomst en tijdstempels
- `bijlage` - bestanden op schijf, metadata in de database
- `verband` - item-item relatie als eigen record

Bijlagen staan onder `ANGELA_UPLOAD_DIR/<item-id>/`. De database bewaart alleen
pad en metadata, nooit de inhoud.

## Lokaal draaien

```
export ANGELA_DB_URL=postgresql://angela_writer:...@localhost:5432/appportal
export ANGELA_UPLOAD_DIR=./data
python app.py
```
