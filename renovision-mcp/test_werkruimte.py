"""Tests op de begrenzing: waar mag een gebruiker bij, en waar niet.

Dit is het deel dat stil fout kan gaan. Een lek in `veilig_pad` of
`mag_schrijven` betekent dat iemand via Claude bij de kopie van een collega
komt, bij de API-sleutel, of bij de manier waarop de VM dingen draait.

Draaien:  cd renovision-mcp && python -m pytest test_werkruimte.py -q
"""
import os
import subprocess
from pathlib import Path

import pytest

import werkruimte as wr
from werkruimte import Geweigerd


def _repo(map_: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=map_, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=map_, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=map_, check=True)


@pytest.fixture()
def basis(tmp_path, monkeypatch):
    """Twee kopieen naast elkaar, zoals op de VM."""
    monkeypatch.setattr(wr, "BASISMAP", tmp_path)
    monkeypatch.setattr(wr, "_timer_actief", lambda naam: "")
    for naam, poort in (("marise", "8104"), ("mukesh", "8106")):
        m = tmp_path / f"globaal-renovision-{naam}"
        (m / "backend").mkdir(parents=True)
        (m / "frontend" / "src").mkdir(parents=True)
        (m / "deploy").mkdir()
        (m / "backend" / "routes.py").write_text("# routes van " + naam)
        (m / "docker-compose.yml").write_text("services: {}")
        (m / "deploy" / "autodeploy.sh").write_text("#!/bin/sh\n")
        (m / ".env").write_text(
            f"COMPOSE_PROJECT_NAME=renovision-{naam}\n"
            f"RENOVISION_PORT={poort}\nANTHROPIC_API_KEY=sk-geheim\n")
        (m / ".env.example").write_text("ANTHROPIC_API_KEY=\n")
        _repo(m)
    return tmp_path


# ---- Ontdekken en toewijzen ----------------------------------------------
def test_ontdekt_kopieen_met_project_en_poort(basis):
    r = wr.ontdek()
    assert set(r) == {"marise", "mukesh"}
    assert r["marise"].project == "renovision-marise"
    assert r["marise"].poort == "8104"
    assert r["marise"].url == "https://renovision-marise.globaal.be"


def test_gebruiker_krijgt_eigen_kopie(basis):
    assert wr.voor_gebruiker("marise").naam == "marise"
    assert wr.voor_gebruiker("MARISE").naam == "marise"


def test_beheerder_valt_niet_terug_op_een_willekeurige_kopie(basis):
    # De admin-kopie bestaat hier niet, dus akadmin hoort niets te krijgen --
    # nooit stilzwijgend die van een collega.
    assert wr.voor_gebruiker("akadmin") is None


def test_onbekende_gebruiker_krijgt_niets(basis):
    assert wr.voor_gebruiker("iemand-anders") is None
    assert wr.voor_gebruiker("") is None


# ---- Padbegrenzing --------------------------------------------------------
@pytest.mark.parametrize("pad", [
    "../globaal-renovision-mukesh/backend/routes.py",   # kopie van een collega
    "../../etc/passwd",
    "/etc/passwd",
    "backend/../../globaal-renovision-mukesh/backend/routes.py",
    "backend/./../../buiten.txt",
])
def test_paden_buiten_de_werkruimte_worden_geweigerd(basis, pad):
    ws = wr.voor_gebruiker("marise")
    with pytest.raises(Geweigerd):
        wr.veilig_pad(ws, pad)


def test_symlink_naar_buiten_wordt_geweigerd(basis):
    ws = wr.voor_gebruiker("marise")
    doelwit = basis / "globaal-renovision-mukesh" / "backend" / "routes.py"
    link = ws.map / "backend" / "gluren.py"
    try:
        os.symlink(doelwit, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks niet beschikbaar")
    with pytest.raises(Geweigerd):
        wr.veilig_pad(ws, "backend/gluren.py")


def test_gewoon_pad_werkt(basis):
    ws = wr.voor_gebruiker("marise")
    p = wr.veilig_pad(ws, "backend/routes.py")
    assert p.read_text().endswith("marise")
    assert wr.relatief(ws, p) == "backend/routes.py"


# ---- Geheimen -------------------------------------------------------------
def test_env_is_niet_leesbaar_maar_env_example_wel():
    assert not wr.leesbaar(".env")
    assert not wr.leesbaar(".env.productie")
    assert wr.leesbaar(".env.example")
    assert wr.leesbaar("backend/server.py")


def test_env_staat_niet_in_de_bestandenlijst(basis):
    ws = wr.voor_gebruiker("marise")
    subprocess.run(["git", "add", "-A", "-f", "."], cwd=ws.map, check=True)
    subprocess.run(["git", "commit", "-qm", "start"], cwd=ws.map, check=True)
    lijst = wr.getrackte_bestanden(ws)
    assert ".env" not in lijst
    assert "backend/routes.py" in lijst


# ---- Schrijfrechten -------------------------------------------------------
@pytest.mark.parametrize("pad", [
    "backend/routes.py", "frontend/src/App.tsx", "tests/test_core.py",
    "README.md",
])
def test_app_code_mag_gewijzigd(pad):
    mag, _ = wr.mag_schrijven(pad)
    assert mag, pad


@pytest.mark.parametrize("pad", [
    "docker-compose.yml",     # kan een host-map in een container hangen
    "deploy/autodeploy.sh",   # draait als ubuntu op de host
    ".env",                   # bevat de API-sleutel
    ".gitignore",
    "yarn.lock",
])
def test_infrastructuur_mag_niet_gewijzigd(pad):
    mag, reden = wr.mag_schrijven(pad)
    assert not mag, pad
    assert reden


def test_schrijven_geeft_een_uitlegbare_reden(basis):
    ws = wr.voor_gebruiker("marise")
    with pytest.raises(Geweigerd) as e:
        wr.controleer_schrijfbaar(ws, "docker-compose.yml")
    assert "beheerder" in str(e.value)


def test_schrijven_geweigerd_zolang_de_autodeploy_draait(basis, monkeypatch):
    monkeypatch.setattr(wr, "_timer_actief",
                        lambda naam: "renovision-marise-deploy.timer")
    ws = wr.voor_gebruiker("marise")
    with pytest.raises(Geweigerd) as e:
        wr.controleer_schrijfbaar(ws, "backend/routes.py")
    assert "twee minuten" in str(e.value)


# ---- Werktak --------------------------------------------------------------
def test_werktak_wordt_aangemaakt_en_hergebruikt(basis):
    ws = wr.voor_gebruiker("marise")
    subprocess.run(["git", "add", "-A"], cwd=ws.map, check=True)
    subprocess.run(["git", "commit", "-qm", "start"], cwd=ws.map, check=True)
    assert wr.zorg_voor_werktak(ws) == "werk/marise"
    assert wr.huidige_tak(ws) == "werk/marise"
    assert wr.zorg_voor_werktak(ws) == "werk/marise"   # tweede keer: geen fout
