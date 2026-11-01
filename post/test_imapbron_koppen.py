"""Een concept als antwoord op een lange mailketen (22-10-2026).

concept_opslaan(antwoord_op=...) faalde met "Header values may not contain
linefeed or carriage return characters": de References-kop van een lange keten
staat over meerdere regels (RFC 5322-vouwing) en _kop liet die regeleinden
staan. Alle adressen en Message-ID's hieronder zijn verzonnen.
"""
import contextlib
import email
import unittest
from unittest.mock import patch

import imapbron

MB = {"adres": "proef@voorbeeld.test", "gebruiker": "proef@voorbeeld.test",
      "imap_host": "imap.voorbeeld.test", "imap_poort": 993}

# Zoals IMAP de kop teruggeeft: CRLF, References en Subject gevouwen.
KOP = (b"From: Klant Proef <klant@voorbeeld.test>\r\n"
       b"Subject: Re: 9999 Proefstraat 1 Proefdorp -\r\n werfbezoek 1\r\n"
       b"Message-ID: <c3@voorbeeld.test>\r\n"
       b"References: <a1@voorbeeld.test>\r\n <b2@voorbeeld.test>\r\n"
       b"\t<x9@voorbeeld.test>\r\n\r\n")


class NepIMAP:
    def __init__(self):
        self.toegevoegd = []

    def select(self, mapnaam, readonly=True):
        return "OK", [b"1"]

    def uid(self, opdracht, uid, deel):
        return "OK", [(b"18869 (BODY[HEADER.FIELDS (...)] {%d}" % len(KOP), KOP), b")"]

    def append(self, mapnaam, vlaggen, datum, inhoud):
        self.toegevoegd.append((mapnaam, inhoud))
        return "OK", [b""]


class Koppen(unittest.TestCase):
    def test_kop_vouwt_open(self):
        self.assertEqual(imapbron._kop("<a1@voorbeeld.test>\r\n <b2@voorbeeld.test>\n\t<x9@voorbeeld.test>"),
                         "<a1@voorbeeld.test> <b2@voorbeeld.test> <x9@voorbeeld.test>")
        self.assertEqual(imapbron._kop("=?utf-8?q?Werfbezoek_caf=C3=A9?=\r\n =?utf-8?q?_deel_2?="),
                         "Werfbezoek café deel 2")
        self.assertNotRegex(imapbron._kop("=?utf-8?q?een=0D=0Atwee?="), "[\r\n]")

    def test_concept_als_antwoord_op_lange_keten(self):
        nep = NepIMAP()
        with patch.object(imapbron, "_Sessie", lambda mb: contextlib.nullcontext(nep)), \
             patch.object(imapbron, "_conceptenmap", lambda M: "INBOX.Drafts"):
            uit = imapbron.concept_opslaan(MB, None, None, "Tussenbericht.", antwoord_op=18869)
        self.assertTrue(uit["opgeslagen"])
        self.assertEqual(uit["antwoord_op"], "<c3@voorbeeld.test>")
        concept = email.message_from_bytes(nep.toegevoegd[0][1])
        self.assertEqual(concept["In-Reply-To"], "<c3@voorbeeld.test>")
        self.assertEqual(concept["References"].split(),
                         ["<a1@voorbeeld.test>", "<b2@voorbeeld.test>", "<x9@voorbeeld.test>",
                          "<c3@voorbeeld.test>"])
        # onderwerp=None: bouw_bericht neemt het gevouwen Subject van de bron over.
        self.assertEqual(uit["onderwerp"], "Re: 9999 Proefstraat 1 Proefdorp - werfbezoek 1")
        self.assertEqual(concept["Subject"], "Re: 9999 Proefstraat 1 Proefdorp - werfbezoek 1")
        self.assertEqual(uit["aan"], ["Klant Proef <klant@voorbeeld.test>"])


if __name__ == "__main__":
    unittest.main()
