--
-- appportal — schema-baseline per 2026-07-01
-- Bron: pg_dump 16.14 --schema-only --no-owner van de live VM-database.
-- Dit bestand is het NULPUNT en wordt nooit meer gewijzigd; alle latere
-- wijzigingen staan als genummerde bestanden in db/migrations/.
--

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: kern; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA kern;


--
-- Name: kosten; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA kosten;


--
-- Name: omv; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA omv;


--
-- Name: schuldentracker; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA schuldentracker;


--
-- Name: citext; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public;


--
-- Name: EXTENSION citext; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION citext IS 'data type for case-insensitive character strings';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: afdeling; Type: TABLE; Schema: kern; Owner: -
--

CREATE TABLE kern.afdeling (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    naam character varying(80) NOT NULL,
    actief boolean DEFAULT true NOT NULL
);


--
-- Name: firma; Type: TABLE; Schema: kern; Owner: -
--

CREATE TABLE kern.firma (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    naam text NOT NULL,
    code text NOT NULL,
    land text NOT NULL,
    actief boolean DEFAULT true NOT NULL
);


--
-- Name: persoon; Type: TABLE; Schema: kern; Owner: -
--

CREATE TABLE kern.persoon (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    hr_nummer character varying(32),
    voornaam character varying(120) NOT NULL,
    achternaam character varying(120),
    email public.citext,
    afdeling_id uuid NOT NULL,
    rol character varying(20) DEFAULT 'Lid'::character varying NOT NULL,
    functie character varying(120),
    authentik_sub character varying(64),
    authentik_username character varying(150),
    in_dienst boolean DEFAULT true NOT NULL,
    datum_in_dienst date,
    datum_uit_dienst date,
    laatste_login timestamp with time zone,
    aangemaakt_op timestamp with time zone DEFAULT now() NOT NULL,
    bijgewerkt_op timestamp with time zone DEFAULT now() NOT NULL,
    locatie character varying(60) DEFAULT 'Suriname'::character varying NOT NULL,
    werkgever_firma_id uuid,
    CONSTRAINT ck_persoon_rol CHECK (((rol)::text = ANY ((ARRAY['Lid'::character varying, 'Hoofd'::character varying, 'Partner'::character varying, 'Management'::character varying])::text[])))
);


--
-- Name: persoon_dienstfirma; Type: TABLE; Schema: kern; Owner: -
--

CREATE TABLE kern.persoon_dienstfirma (
    persoon_id uuid NOT NULL,
    firma_id uuid NOT NULL
);


--
-- Name: account; Type: TABLE; Schema: kosten; Owner: -
--

CREATE TABLE kosten.account (
    id bigint NOT NULL,
    software_id bigint NOT NULL,
    naam text,
    owner_persoon_id uuid,
    is_shared boolean DEFAULT false NOT NULL,
    note text
);


--
-- Name: account_id_seq; Type: SEQUENCE; Schema: kosten; Owner: -
--

ALTER TABLE kosten.account ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME kosten.account_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: assumption; Type: TABLE; Schema: kosten; Owner: -
--

CREATE TABLE kosten.assumption (
    sleutel text NOT NULL,
    waarde text NOT NULL
);


--
-- Name: charge_actual; Type: TABLE; Schema: kosten; Owner: -
--

CREATE TABLE kosten.charge_actual (
    id bigint NOT NULL,
    firma_id text NOT NULL,
    vendor text NOT NULL,
    jaar integer NOT NULL,
    maand integer NOT NULL,
    bedrag_eur numeric(12,2) NOT NULL
);


--
-- Name: charge_actual_id_seq; Type: SEQUENCE; Schema: kosten; Owner: -
--

ALTER TABLE kosten.charge_actual ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME kosten.charge_actual_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: firma; Type: TABLE; Schema: kosten; Owner: -
--

CREATE TABLE kosten.firma (
    id text NOT NULL,
    naam text NOT NULL,
    officieel boolean DEFAULT true NOT NULL
);


--
-- Name: seat; Type: TABLE; Schema: kosten; Owner: -
--

CREATE TABLE kosten.seat (
    id bigint NOT NULL,
    account_id bigint NOT NULL,
    persoon_id uuid,
    note text
);


--
-- Name: seat_id_seq; Type: SEQUENCE; Schema: kosten; Owner: -
--

ALTER TABLE kosten.seat ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME kosten.seat_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: software; Type: TABLE; Schema: kosten; Owner: -
--

CREATE TABLE kosten.software (
    id bigint NOT NULL,
    firma_id text NOT NULL,
    vendor text NOT NULL,
    plan text,
    seats_owned integer,
    unit_price numeric(12,2),
    currency text DEFAULT 'EUR'::text NOT NULL,
    billing_cycle text,
    payment_method text DEFAULT 'VISA'::text NOT NULL,
    admin text,
    decision text,
    dest_firma_id text,
    is_bundle boolean DEFAULT false NOT NULL,
    notice text,
    end_date text,
    note text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: software_id_seq; Type: SEQUENCE; Schema: kosten; Owner: -
--

ALTER TABLE kosten.software ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME kosten.software_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: taak; Type: TABLE; Schema: omv; Owner: -
--

CREATE TABLE omv.taak (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    persoon_id uuid NOT NULL,
    titel character varying(200) NOT NULL,
    status character varying(32) DEFAULT 'todo'::character varying NOT NULL,
    deadline date
);


--
-- Name: factuur; Type: TABLE; Schema: schuldentracker; Owner: -
--

CREATE TABLE schuldentracker.factuur (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    persoon_id uuid NOT NULL,
    bedrag numeric(12,2) NOT NULL,
    status character varying(32) DEFAULT 'open'::character varying NOT NULL,
    aangemaakt_op timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: afdeling afdeling_naam_key; Type: CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.afdeling
    ADD CONSTRAINT afdeling_naam_key UNIQUE (naam);


--
-- Name: afdeling afdeling_pkey; Type: CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.afdeling
    ADD CONSTRAINT afdeling_pkey PRIMARY KEY (id);


--
-- Name: firma firma_code_key; Type: CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.firma
    ADD CONSTRAINT firma_code_key UNIQUE (code);


--
-- Name: firma firma_pkey; Type: CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.firma
    ADD CONSTRAINT firma_pkey PRIMARY KEY (id);


--
-- Name: persoon persoon_authentik_sub_key; Type: CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.persoon
    ADD CONSTRAINT persoon_authentik_sub_key UNIQUE (authentik_sub);


--
-- Name: persoon_dienstfirma persoon_dienstfirma_pkey; Type: CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.persoon_dienstfirma
    ADD CONSTRAINT persoon_dienstfirma_pkey PRIMARY KEY (persoon_id, firma_id);


--
-- Name: persoon persoon_email_key; Type: CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.persoon
    ADD CONSTRAINT persoon_email_key UNIQUE (email);


--
-- Name: persoon persoon_hr_nummer_key; Type: CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.persoon
    ADD CONSTRAINT persoon_hr_nummer_key UNIQUE (hr_nummer);


--
-- Name: persoon persoon_pkey; Type: CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.persoon
    ADD CONSTRAINT persoon_pkey PRIMARY KEY (id);


--
-- Name: account account_pkey; Type: CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.account
    ADD CONSTRAINT account_pkey PRIMARY KEY (id);


--
-- Name: assumption assumption_pkey; Type: CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.assumption
    ADD CONSTRAINT assumption_pkey PRIMARY KEY (sleutel);


--
-- Name: charge_actual charge_actual_firma_id_vendor_jaar_maand_key; Type: CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.charge_actual
    ADD CONSTRAINT charge_actual_firma_id_vendor_jaar_maand_key UNIQUE (firma_id, vendor, jaar, maand);


--
-- Name: charge_actual charge_actual_pkey; Type: CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.charge_actual
    ADD CONSTRAINT charge_actual_pkey PRIMARY KEY (id);


--
-- Name: firma firma_pkey; Type: CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.firma
    ADD CONSTRAINT firma_pkey PRIMARY KEY (id);


--
-- Name: seat seat_pkey; Type: CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.seat
    ADD CONSTRAINT seat_pkey PRIMARY KEY (id);


--
-- Name: software software_firma_id_vendor_key; Type: CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.software
    ADD CONSTRAINT software_firma_id_vendor_key UNIQUE (firma_id, vendor);


--
-- Name: software software_pkey; Type: CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.software
    ADD CONSTRAINT software_pkey PRIMARY KEY (id);


--
-- Name: taak taak_pkey; Type: CONSTRAINT; Schema: omv; Owner: -
--

ALTER TABLE ONLY omv.taak
    ADD CONSTRAINT taak_pkey PRIMARY KEY (id);


--
-- Name: factuur factuur_pkey; Type: CONSTRAINT; Schema: schuldentracker; Owner: -
--

ALTER TABLE ONLY schuldentracker.factuur
    ADD CONSTRAINT factuur_pkey PRIMARY KEY (id);


--
-- Name: ix_persoon_afdeling_id; Type: INDEX; Schema: kern; Owner: -
--

CREATE INDEX ix_persoon_afdeling_id ON kern.persoon USING btree (afdeling_id);


--
-- Name: ix_persoon_authentik_username; Type: INDEX; Schema: kern; Owner: -
--

CREATE INDEX ix_persoon_authentik_username ON kern.persoon USING btree (authentik_username);


--
-- Name: seat_persoon_idx; Type: INDEX; Schema: kosten; Owner: -
--

CREATE INDEX seat_persoon_idx ON kosten.seat USING btree (persoon_id);


--
-- Name: ix_taak_persoon_id; Type: INDEX; Schema: omv; Owner: -
--

CREATE INDEX ix_taak_persoon_id ON omv.taak USING btree (persoon_id);


--
-- Name: ix_factuur_persoon_id; Type: INDEX; Schema: schuldentracker; Owner: -
--

CREATE INDEX ix_factuur_persoon_id ON schuldentracker.factuur USING btree (persoon_id);


--
-- Name: persoon persoon_afdeling_id_fkey; Type: FK CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.persoon
    ADD CONSTRAINT persoon_afdeling_id_fkey FOREIGN KEY (afdeling_id) REFERENCES kern.afdeling(id) ON DELETE RESTRICT;


--
-- Name: persoon_dienstfirma persoon_dienstfirma_firma_id_fkey; Type: FK CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.persoon_dienstfirma
    ADD CONSTRAINT persoon_dienstfirma_firma_id_fkey FOREIGN KEY (firma_id) REFERENCES kern.firma(id);


--
-- Name: persoon_dienstfirma persoon_dienstfirma_persoon_id_fkey; Type: FK CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.persoon_dienstfirma
    ADD CONSTRAINT persoon_dienstfirma_persoon_id_fkey FOREIGN KEY (persoon_id) REFERENCES kern.persoon(id) ON DELETE CASCADE;


--
-- Name: persoon persoon_werkgever_firma_id_fkey; Type: FK CONSTRAINT; Schema: kern; Owner: -
--

ALTER TABLE ONLY kern.persoon
    ADD CONSTRAINT persoon_werkgever_firma_id_fkey FOREIGN KEY (werkgever_firma_id) REFERENCES kern.firma(id);


--
-- Name: account account_software_id_fkey; Type: FK CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.account
    ADD CONSTRAINT account_software_id_fkey FOREIGN KEY (software_id) REFERENCES kosten.software(id) ON DELETE CASCADE;


--
-- Name: charge_actual charge_actual_firma_id_fkey; Type: FK CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.charge_actual
    ADD CONSTRAINT charge_actual_firma_id_fkey FOREIGN KEY (firma_id) REFERENCES kosten.firma(id);


--
-- Name: seat seat_account_id_fkey; Type: FK CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.seat
    ADD CONSTRAINT seat_account_id_fkey FOREIGN KEY (account_id) REFERENCES kosten.account(id) ON DELETE CASCADE;


--
-- Name: software software_dest_firma_id_fkey; Type: FK CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.software
    ADD CONSTRAINT software_dest_firma_id_fkey FOREIGN KEY (dest_firma_id) REFERENCES kosten.firma(id);


--
-- Name: software software_firma_id_fkey; Type: FK CONSTRAINT; Schema: kosten; Owner: -
--

ALTER TABLE ONLY kosten.software
    ADD CONSTRAINT software_firma_id_fkey FOREIGN KEY (firma_id) REFERENCES kosten.firma(id);


--
-- Name: taak taak_persoon_id_fkey; Type: FK CONSTRAINT; Schema: omv; Owner: -
--

ALTER TABLE ONLY omv.taak
    ADD CONSTRAINT taak_persoon_id_fkey FOREIGN KEY (persoon_id) REFERENCES kern.persoon(id) ON DELETE RESTRICT;


--
-- Name: factuur factuur_persoon_id_fkey; Type: FK CONSTRAINT; Schema: schuldentracker; Owner: -
--

ALTER TABLE ONLY schuldentracker.factuur
    ADD CONSTRAINT factuur_persoon_id_fkey FOREIGN KEY (persoon_id) REFERENCES kern.persoon(id) ON DELETE RESTRICT;


--
-- Name: SCHEMA kern; Type: ACL; Schema: -; Owner: -
--

GRANT USAGE ON SCHEMA kern TO portal;
GRANT USAGE ON SCHEMA kern TO kosten;
GRANT USAGE ON SCHEMA kern TO medewerker_writer;


--
-- Name: SCHEMA kosten; Type: ACL; Schema: -; Owner: -
--

GRANT USAGE ON SCHEMA kosten TO kosten;
GRANT USAGE ON SCHEMA kosten TO portal;


--
-- Name: SCHEMA omv; Type: ACL; Schema: -; Owner: -
--

GRANT USAGE ON SCHEMA omv TO portal;


--
-- Name: SCHEMA schuldentracker; Type: ACL; Schema: -; Owner: -
--

GRANT USAGE ON SCHEMA schuldentracker TO portal;


--
-- Name: TABLE afdeling; Type: ACL; Schema: kern; Owner: -
--

GRANT SELECT ON TABLE kern.afdeling TO portal;
GRANT SELECT ON TABLE kern.afdeling TO kosten;


--
-- Name: TABLE firma; Type: ACL; Schema: kern; Owner: -
--

GRANT SELECT ON TABLE kern.firma TO portal;
GRANT SELECT ON TABLE kern.firma TO medewerker_writer;


--
-- Name: TABLE persoon; Type: ACL; Schema: kern; Owner: -
--

GRANT SELECT ON TABLE kern.persoon TO portal;
GRANT SELECT ON TABLE kern.persoon TO kosten;
GRANT SELECT ON TABLE kern.persoon TO medewerker_writer;


--
-- Name: COLUMN persoon.werkgever_firma_id; Type: ACL; Schema: kern; Owner: -
--

GRANT UPDATE(werkgever_firma_id) ON TABLE kern.persoon TO medewerker_writer;


--
-- Name: TABLE persoon_dienstfirma; Type: ACL; Schema: kern; Owner: -
--

GRANT SELECT ON TABLE kern.persoon_dienstfirma TO portal;
GRANT SELECT,INSERT,DELETE ON TABLE kern.persoon_dienstfirma TO medewerker_writer;


--
-- Name: TABLE account; Type: ACL; Schema: kosten; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE kosten.account TO kosten;
GRANT SELECT ON TABLE kosten.account TO portal;


--
-- Name: SEQUENCE account_id_seq; Type: ACL; Schema: kosten; Owner: -
--

GRANT SELECT,USAGE ON SEQUENCE kosten.account_id_seq TO kosten;


--
-- Name: TABLE assumption; Type: ACL; Schema: kosten; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE kosten.assumption TO kosten;
GRANT SELECT ON TABLE kosten.assumption TO portal;


--
-- Name: TABLE charge_actual; Type: ACL; Schema: kosten; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE kosten.charge_actual TO kosten;
GRANT SELECT ON TABLE kosten.charge_actual TO portal;


--
-- Name: SEQUENCE charge_actual_id_seq; Type: ACL; Schema: kosten; Owner: -
--

GRANT SELECT,USAGE ON SEQUENCE kosten.charge_actual_id_seq TO kosten;


--
-- Name: TABLE firma; Type: ACL; Schema: kosten; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE kosten.firma TO kosten;
GRANT SELECT ON TABLE kosten.firma TO portal;


--
-- Name: TABLE seat; Type: ACL; Schema: kosten; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE kosten.seat TO kosten;
GRANT SELECT ON TABLE kosten.seat TO portal;


--
-- Name: SEQUENCE seat_id_seq; Type: ACL; Schema: kosten; Owner: -
--

GRANT SELECT,USAGE ON SEQUENCE kosten.seat_id_seq TO kosten;


--
-- Name: TABLE software; Type: ACL; Schema: kosten; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE kosten.software TO kosten;
GRANT SELECT ON TABLE kosten.software TO portal;


--
-- Name: SEQUENCE software_id_seq; Type: ACL; Schema: kosten; Owner: -
--

GRANT SELECT,USAGE ON SEQUENCE kosten.software_id_seq TO kosten;


--
-- Name: TABLE taak; Type: ACL; Schema: omv; Owner: -
--

GRANT SELECT ON TABLE omv.taak TO portal;


--
-- Name: TABLE factuur; Type: ACL; Schema: schuldentracker; Owner: -
--

GRANT SELECT ON TABLE schuldentracker.factuur TO portal;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: kosten; Owner: -
--

ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA kosten GRANT SELECT ON TABLES TO portal;
ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA kosten GRANT SELECT,INSERT,DELETE,UPDATE ON TABLES TO kosten;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: omv; Owner: -
--

ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA omv GRANT SELECT ON TABLES TO portal;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: schuldentracker; Owner: -
--

ALTER DEFAULT PRIVILEGES FOR ROLE authentik IN SCHEMA schuldentracker GRANT SELECT ON TABLES TO portal;


--
-- PostgreSQL database dump complete
--
