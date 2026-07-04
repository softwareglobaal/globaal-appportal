-- 035 - verrijking van het oproep-archief (laag 2c: veldsemantiek).
--
-- De lijst-respons van /communications bevat geen deelnemers; die zitten
-- alleen in het detail-record per oproep (zelfde les als bij phonelines).
-- De poller haalt daarom per nieuw record het detail op (gedoseerd per tick)
-- en zet de geleerde semantiek vast:
--   beantwoord   - callAnswerTime aanwezig = opgenomen; leeg = gemist
--   antwoord_sec - hoe snel er opgenomen werd
--   lijn_oid     - phoneLine.oid: directe koppeling naar de belvolgorde-
--                  spiegel en daarmee naar ons nummerregister (sterkere match
--                  dan deelnemer-adressen, want dat zijn de nummers van de
--                  bellers zelf)
--   verrijkt_op  - wanneer het detail is opgehaald (NULL = wachtrij)

ALTER TABLE communicatie.xelion_communicatie
    ADD COLUMN beantwoord   boolean,
    ADD COLUMN antwoord_sec integer,
    ADD COLUMN lijn_oid     text,
    ADD COLUMN verrijkt_op  timestamptz;

-- De verrijkings-wachtrij: klein deelindex op wat nog moet.
CREATE INDEX ix_xelion_comm_wachtrij
    ON communicatie.xelion_communicatie (datum DESC)
    WHERE verrijkt_op IS NULL;
