"""Microsofts 'User is authenticated but not connected' is tijdelijk: de postbus probeert opnieuw (22-10-2026)."""
import imaplib
import unittest
from unittest.mock import patch

import imapbron

MB = {"adres": "proef@hotmail.com", "gebruiker": "proef@hotmail.com", "imap_host": "outlook.office365.com",
      "imap_poort": 993, "auth": "microsoft"}


class NepIMAP:
    pogingen = 0
    fouten = 0

    def __init__(self, *a, **k):
        pass

    def authenticate(self, *a):
        NepIMAP.pogingen += 1
        if NepIMAP.pogingen <= NepIMAP.fouten:
            raise imaplib.IMAP4.error("AUTHENTICATE failed: User is authenticated but not connected.")
        return "OK", [b""]

    def logout(self):
        return "BYE", [b""]


class Herkans(unittest.TestCase):
    def setUp(self):
        NepIMAP.pogingen = 0
        imapbron._pool.clear()
        self.p = [patch.object(imapbron.imaplib, "IMAP4_SSL", NepIMAP),
                  patch.object(imapbron.oauth_ms, "toegangstoken", lambda m: "token"),
                  patch.object(imapbron.oauth_ms, "xoauth2", lambda g, t: "x"),
                  patch.object(imapbron.time, "sleep", lambda s: None)]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_tweede_poging_lukt(self):
        NepIMAP.fouten = 2
        with imapbron._Sessie(MB) as M:
            self.assertIsInstance(M, NepIMAP)
        self.assertEqual(NepIMAP.pogingen, 3)

    def test_blijvend_niet_verbonden_zegt_niet_koppel_opnieuw(self):
        NepIMAP.fouten = 99
        with self.assertRaises(ValueError) as fout:
            with imapbron._Sessie(MB):
                pass
        self.assertEqual(NepIMAP.pogingen, len(imapbron.HERKANS_NIET_VERBONDEN) + 1)
        self.assertNotIn("oauth_koppel", str(fout.exception))
        self.assertIn("tijdelijk", str(fout.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
