"""Grendel: geen echte namen, gevoelige onderwerpen of echte adressen in de testbestanden van regie-zoom.

De repo is publiek. Op 22-10-2026 stonden in de nieuwe tests van de branch regie-zoom echte voornamen, gevoelige
onderwerpen uit het privéleven van de eigenaar en echte e-mailadressen van collega's als proefgegevens. Ze zijn
vervangen door verzonnen gegevens (Proefpersoon Zeta, Proefonderwerp Omega, adressen op .test). Deze grendel houdt dat
zo: hij leest de testbestanden die die branch toevoegde of wijzigde, splitst de tekst in woorden (kleine letters;
letters, cijfers, @, punt en koppelteken) en faalt als de sha256 van een woord, of van een deel ervan tussen @, punt of
koppelteken, in VERBODEN staat. De woorden zelf staan nergens in de repo, ook niet in een foutmelding: die noemt alleen
bestand, regel en het begin van de hash.

Een woord erbij: reken de hash buiten de repo uit, met
    python3 -c "import hashlib; print(hashlib.sha256('<woord in kleine letters>'.encode()).hexdigest())"
en zet alleen die hash in VERBODEN. Een testbestand erbij: zet het pad in BESTANDEN.
Draaien: python3 mijnagents-runner/tests/test_geen_echte_namen.py
"""
import hashlib
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))

# Testbestanden uit regie-zoom en zoom-accountscan, plus deze grendel zelf.
BESTANDEN = (
    "mijnagents-runner/tests/test_bode_regie.py",
    "mijnagents-runner/tests/test_bord_lees.py",
    "mijnagents-runner/tests/test_codex_ronde2_bode.py",
    "mijnagents-runner/tests/test_dagbundelaar.py",
    "mijnagents-runner/tests/test_geen_echte_namen.py",
    "mijnagents-runner/tests/test_keten.py",
    "mijnagents-runner/tests/test_plaud_wacht.py",
    "mijnagents-runner/tests/test_regisseur.py",
    "mijnagents-runner/tests/test_taken.py",
    "mijnagents-runner/tests/test_uitrol_regie.py",
    "mijnagents-runner/tests/test_uitvoerder_signaal.py",
    "mijnagents-runner/tests/test_whatsapp.py",
    "mijnagents-runner/tests/test_zoom_account.py",
    "mijnagents-runner/tests/test_zoom_wacht.py",
    "mijnagents-runner/tests/fixtures/zoom_leesapp_scopes.txt",
    "mijnagents/test_gesprekken_api.py",
)

# Elke hash staat voor een echt gegeven uit het privéleven van de eigenaar of van een collega: voornamen, gevoelige
# onderwerpen, echte e-mailadressen en een klantnaam. Bewust zonder de woorden zelf; ze horen niet in een publieke repo.
VERBODEN = frozenset({
    "2b2a0ff8f9def3f17d58512ab10d7b1b40e5ae06dabbddfd4d9278a428a3700c",
    "79a6a933dfc9b1975e444d4e8481c64c771d8ab40b7ac72f8bc1a1bca1718bef",
    "3f2e23b2ee1991da34bdc689a44a229d1b64f3b617d6569ffb6e19f760acfded",
    "e5e6142a3cca2fe80abb44a1e6ffe5ff6f2e456ac50d9ccf8a8fe649b7ed2055",
    "84d23e48c000602e3d66f380e6ef4697bf4006bc106391140ca44eda2d7d54b9",
    "72d5dd740b9afefff867fd4303ac7ab429877428507f2eab9b2f15ada8b9f415",
    "c74476b09d52d3a2feeed3f48fcf8cc5bd91c09636a3c583a8422d11f5784e7b",
    "c0d7a457c0cce76263ffef0bd0e9ec3435416d0d1693e60b930e6886756ab641",
    "039b1751609c775495c4bf7d4218285157cb920f11ea769b373bb1aa3ffe661d",
    "6f62ecf22c1d04cb33ce70c813f5f7fb74657c8ba7d61a9f1ef22ee65de744e7",
    "2ec2e50458b9009d9367a6fcba0ea24640d259f3bdc81845871e532f08a2f433",
    "b9040e4f1c071a605e3f5852133385ada24f6695e5b26d7d864e0262436ad05f",
    "884e4492accb5d278b2a2039936f2714df5d4177cfea730cec2ad622a9d2e200",
    "a795ab67a0a69ae51e3df396832e4746b1757f029d2431f86caf07674e90741b",
    "b3bfac5c26330023bc5ab0e5befc33ba975dee4508347f8da262c310ef6303f5",   # klantnaam, 22-10-2026
})

WOORD = re.compile(r"(?:[^\W_]|[@.\-])+")
DELEN = re.compile(r"[@.\-]+")


def _hash(woord):
    return hashlib.sha256(woord.encode("utf-8")).hexdigest()


def woorden(tekst):
    """Elk woord in kleine letters, zonder punt of koppelteken aan het begin of einde, en daarna zijn delen tussen @,
    punt of koppelteken (zo valt ook een naam in een adres of in een samenstelling met koppelteken op)."""
    for w in WOORD.findall(tekst.lower()):
        w = w.strip(".-")
        if not w:
            continue
        yield w
        for deel in DELEN.split(w):
            if deel and deel != w:
                yield deel


def treffers(tekst, verboden=VERBODEN):
    """[(regelnummer, begin van de hash)] van elk verboden woord; nooit het woord zelf."""
    uit = []
    for nr, regel in enumerate(tekst.splitlines(), start=1):
        for w in woorden(regel):
            h = _hash(w)
            if h in verboden:
                uit.append((nr, h[:12]))
    return uit


def test_de_lijsten_zijn_volledig():
    assert len(VERBODEN) == 15 and all(re.fullmatch(r"[0-9a-f]{64}", h) for h in VERBODEN), "vijftien sha256-hashes"
    assert len(set(BESTANDEN)) == len(BESTANDEN), "een bestand staat twee keer in BESTANDEN"
    ontbreekt = [p for p in BESTANDEN if not os.path.isfile(os.path.join(REPO, p))]
    assert not ontbreekt, f"deze testbestanden bestaan niet meer (hernoemd? pas BESTANDEN aan): {ontbreekt}"
    fixtures = os.path.join(REPO, "mijnagents-runner", "tests", "fixtures")
    fixture_paden = {os.path.relpath(os.path.join(mapnaam, naam), REPO)
                    for mapnaam, _, namen in os.walk(fixtures) for naam in namen
                    if not naam.startswith(".") and not naam.endswith((".pyc", ".pyo"))}
    assert fixture_paden <= set(BESTANDEN), "een fixture staat buiten de namengrendel"
    workflow = os.path.join(REPO, ".github", "workflows", "regie-grendels.yml")
    with open(workflow, encoding="utf-8") as f:
        ci_tests = set(re.findall(r"- run: python3 (mijnagents-runner/tests/test_[^\s]+\.py)", f.read()))
    assert ci_tests <= set(BESTANDEN), "een CI-testbestand staat buiten de namengrendel"


def test_de_grendel_vangt_een_woord_in_elke_vorm():
    """Met een verzonnen woord en een verzonnen adres: hoofdletters, leestekens, een adres in een sleutel, een adres
    aan het einde van een zin en een naam met koppelteken of in een adres vallen allemaal op."""
    proef = frozenset({_hash("zetaproef"), _hash("iemand@kantoor.test")})
    for tekst in ("Zetaproef", "'ZETAPROEF',", "Avond met Zetaproef.", "Avond-met-Zetaproef", "zetaproef@elders.test",
                  "zoom:chat:iemand@kantoor.test:2026-10-20", "Mail naar Iemand@Kantoor.TEST.", "(iemand@kantoor.test)"):
        assert treffers(tekst, proef), tekst
    for tekst in ("Proefpersoon Zeta", "zetaproefje", "niemand@kantoor.test", "iemand@kantoor.testen"):
        assert not treffers(tekst, proef), tekst
    assert treffers("eerste regel\ntweede met Zetaproef", proef) == [(2, _hash("zetaproef")[:12])]


def test_geen_echte_namen_in_de_testbestanden():
    gevonden = []
    for pad in BESTANDEN:
        with open(os.path.join(REPO, pad), encoding="utf-8") as f:
            gevonden += [f"{pad}:{nr} (hash {h})" for nr, h in treffers(f.read())]
    assert not gevonden, ("een echt gegeven uit het privéleven of van een collega staat in een test; vervang het door "
                          "een verzonnen proefgegeven:\n  " + "\n  ".join(gevonden))


if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                f()
                goed += 1
                print(f"   geslaagd  {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"   GEFAALD   {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)
