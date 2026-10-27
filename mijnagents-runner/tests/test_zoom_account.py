"""Fase 4b: verzonnen Zoom-antwoorden, geen netwerk en geen echte accountgegevens."""
import io
import importlib.util
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "koppelingen"))
import zoom as Z  # noqa: E402
import zoom_account as ZA  # noqa: E402

KLOK = datetime(2026, 10, 26, 7, tzinfo=timezone.utc)
# De Zoomarchivaris (27-10-2026): ZA-01 is pas open als alle opnames bewezen in Dropbox staan. De bestaande proeven gaan
# uit van een volledige kopie; test_zoom_archief.py toetst de wachtstand. Nooit het echte bestand op de VM.
ZA.ARCHIEF_DEKKING = os.path.join(tempfile.mkdtemp(prefix="zoom-account-"), "dekking.json")
ZA.archief_ronde_geslaagd = lambda ts: True  # het bord van De Zoomarchivaris: test_zoom_archief.py toetst dat apart
with open(ZA.ARCHIEF_DEKKING, "w", encoding="utf-8") as _f:
    json.dump({"ts": datetime.now(timezone.utc).isoformat(), "dekking": True, "wisregel_veilig": True}, _f)


def proefstand():
    return {
        "account": {"recording.auto_delete_cmr": False, "in_meeting.waiting_room": True,
                    "recording.cloud_recording": True, "ai.ai_model_type": "Federated",
                    "ai.meeting_summary.enable": True, "ai.meeting_summary_retention.enable": False,
                    "recording.record_speaker_view": True, "recording.record_gallery_view": False,
                    "recording.record_files_separately.active_speaker": False,
                    "recording.record_files_separately.gallery_view": True,
                    "recording.record_files_separately.shared_screen": False},
        "security": {"tweestaps": "role", "rollen": ["owner"], "afmelden": "uit", "facebook": True, "sms": None},
        "locks": {"wachtkamer": True, "toegangscode": False, "velden": {"in_meeting.waiting_room": True}, "aantal": 2},
        "meeting_security": {"meeting_security.meeting_password": True},
        "user": {"recording.auto_recording": "cloud", "recording.recording_audio_transcript": True,
                 "recording.record_audio_file": False, "opslaglocatie": "CH", "landen": ["CH", "DE"],
                 "recording.record_speaker_view": True, "recording.record_gallery_view": False,
                 "recording.record_files_separately.active_speaker": False,
                 "recording.record_files_separately.gallery_view": True,
                 "recording.record_files_separately.shared_screen": False},
        "ruimte": {"wachtkamer": True, "toegangscode": False, "voor_host": False},
        "rollen": {"standaard": {"Owner": 1, "Admin": 1, "Member": 7}, "eigen_leeg": 1,
                   "eigen_met": 0, "beheer_ids": {"Owner": "owner", "Admin": "admin"}},
        "groepen": {"aantal": 3, "leeg": 1, "leden": 8},
        "opslag": {"stand": "ok", "gratis_gb": 10, "betaald_gb": 0, "gebruikt_gb": 8.8,
                   "pct": 88, "groei_gb_per_dag": 0.3, "vol_rond": "2026-10-30", "vol_dagen": 4},
        "opslagtrend": {"stand": "ok"},
        "opnames": {"stand": "ok", "aantal": 8, "video_pct": 95, "klaar": 8, "met_transcript": 8,
                    "transcript_pct": 100},
        "samenvattingen": {"aantal": 9},
        "apps": {"stand": "ok", "aantal": 1, "eigen": 0,
                 "overzicht": [{"code": "abcdefghijklmnop", "naam": "externe app", "gepubliceerd": True,
                                "rechten": 10, "schrijf": 6}],
                 "met_schrijfrechten": [{"code": "abcdefghijklmnop", "naam": "externe app",
                                         "gepubliceerd": True, "rechten": 10, "schrijf": 6}]},
        "logboek": {"aantal": 16, "tellingen": {"User Settings / REST API - Update": 13},
                    "regels": {}, "gevoelig": {}},
        "samenvatting": {"licensed": 4, "basic": 7, "room": 0, "pending": 1},
        "pakket": {"stand": "ok", "periode": "monthly", "hosts": 4,
                   "sinds": "2026-04-01", "volgende_factuur": "2026-11-01"},
        "facturen": {"stand": "onbekend: factuurlijst leeg bij lopend pakket"},
        "rapport_actief": {"aantal": 6}, "rapport_inactief": {"aantal": 2},
        "gebruikers": {"login_types": {}, "aantal": 11},
        "daggebruik": {"stand": "ok", "meetings": 10},
    }


def _weigert(f):
    try:
        f()
    except (Z.Geweigerd, Z.AccountFout, ZA.PrivacyFout):
        return
    raise AssertionError("de grendel liet de proef door")


def test_a01_a05_accountpaden_alleen_get_en_alleen_leesapp():
    oud = dict(Z._VAST)
    Z.vastzetten("vaste-id", ["9100000001"])
    gezien = []
    def vraag(url, koppen):
        gezien.append((url, koppen))
        return 200, "", b"{}"
    try:
        with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
             patch.object(Z, "leesapp_verboden", return_value=[]), \
             patch.object(Z, "_toegang", side_effect=lambda profiel: {"lees": "lees-token"}[profiel]), \
             patch.object(Z, "_vraag", side_effect=vraag):
            for patroon in Z.ACCOUNT_PADEN:
                pad = patroon.replace("[^/]+", "vaste-id").replace(r"\d+", "9100000001").replace("[A-Za-z0-9_-]{6,64}", "abcdef")
                Z.lees_account(pad)
            for pad, params in (("/users", {"status": "active", "page_size": 300}),
                                ("/accounts/me/settings", {"option": "security"}),
                                ("/report/operationlogs", {"from": "2026-10-01", "to": "2026-10-26"})):
                Z.lees_account(pad, params)
            verwacht = len(Z.ACCOUNT_PADEN) + 3
            assert len(gezien) == verwacht and all(k["Authorization"] == "Bearer lees-token" for _, k in gezien)
            for pad in ("/users/ander-id/settings", "/chat/users/x/messages", "/accounts/me/recordings?include_fields=x",
                        "/meetings/123/recordings", "/meetings/9100000002", "/metrics/meetings", "/report/billing", "/im/groups",
                        "/accounts/me/%2e/settings", "/accounts/me/settings#x", "/accounts/../me/settings"):
                _weigert(lambda pad=pad: Z.lees_account(pad))
            _weigert(lambda: Z.lees_account("/accounts/me/settings", methode="POST"))
            _weigert(lambda: Z.lees_account("/accounts/me/settings", {"include_fields": "email"}))
            _weigert(lambda: Z.lees_account("/accounts/me/settings", {"option": "x"}))
            _weigert(lambda: Z.lees_account("/users", {"next_page_token": "voornaam@voorbeeld.test"}))
            _weigert(lambda: Z.lees("/accounts/me/settings"))
            assert len(gezien) == verwacht
            Z.vastzetten(None)
            _weigert(lambda: Z.lees_account("/users/summary"))
            assert len(gezien) == verwacht
    finally:
        Z._VAST.update(oud)


def test_a04_a06_a07_a09_token_fout_recht_en_limiet_zonder_vrije_tekst():
    oud = dict(Z._VAST)
    Z.vastzetten("vaste-id")
    try:
        with patch.object(Z, "leesapp", return_value=False), patch.object(Z, "_vraag", side_effect=AssertionError("netwerk")):
            _weigert(lambda: Z.lees_account("/users/summary"))
        with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
             patch.object(Z, "leesapp_verboden", return_value=[]), \
             patch.object(Z, "_toegang", side_effect=lambda profiel: {"lees": "lees-token"}[profiel]):
            with patch.object(Z, "_vraag", return_value=(400, "", b'{"code":200,"message":"voornaam@voorbeeld.test trace"}')):
                try:
                    Z.lees_account("/users/summary")
                except Z.AccountFout as e:
                    assert e.http == 400 and e.zoomcode == 200 and "@" not in str(e)
                else:
                    raise AssertionError("400 moest onbekend blijven")
            with patch.object(Z, "_vraag", return_value=(429, "", b"{}")):
                try:
                    Z.lees_account("/users/summary")
                except Z.AccountFout as e:
                    assert e.http == 429
                else:
                    raise AssertionError("429 moest stoppen")
    finally:
        Z._VAST.update(oud)


def test_za2_leesapp_token_fout_of_verboden_valt_nooit_op_stack_terug():
    vast = dict(Z._VAST)
    tokens = dict(Z._tokens)
    Z.vastzetten("vaste-id")
    try:
        for antwoord in (Z.ZoomFout("geen leestoken"),
                         {"access_token": "verboden-token", "scope": "user:read:zak:admin", "expires_in": 3600}):
            Z._tokens.clear()
            gevraagd = []
            def token(cid, geheim, account):
                gevraagd.append((cid, account))
                if cid != "lees-id":
                    raise AssertionError("stack-app geraadpleegd")
                if isinstance(antwoord, Exception):
                    raise antwoord
                return antwoord
            with patch.object(Z, "_lees_sleutel", side_effect=lambda naam: {
                    "ZOOM_LEES_CLIENT_ID": "lees-id", "ZOOM_LEES_CLIENT_SECRET": "lees-geheim",
                    "ZOOM_LEES_ACCOUNT_ID": "lees-account"}.get(naam, "")), \
                 patch.object(Z, "_sleutel", side_effect=lambda naam: {
                     "ZOOM_CLIENT_ID": "stack-id", "ZOOM_CLIENT_SECRET": "stack-geheim",
                     "ZOOM_ACCOUNT_ID": "stack-account"}.get(naam, "")), \
                 patch.object(Z, "leesapp_fout", return_value=""), patch.object(Z, "leesapp_verboden", return_value=[]), \
                 patch.object(Z, "token_halen", side_effect=token), \
                 patch.object(Z, "_vraag", side_effect=AssertionError("Zoom benaderd")):
                _weigert(lambda: Z.lees_account("/users/summary"))
            assert gevraagd == [("lees-id", "lees-account")]
    finally:
        Z._tokens.clear()
        Z._tokens.update(tokens)
        Z._VAST.update(vast)


def test_a08_m4_lijst_zonder_sleutel_en_afgekapt_is_onbekend():
    with patch.object(Z, "lees_account", return_value={"total_records": 5}):
        _weigert(lambda: Z.lees_account_alles("/marketplace/apps", {"type": "account_added"}, "apps"))
    with patch.object(Z, "lees_account", return_value={"apps": [], "next_page_token": "verder"}):
        _weigert(lambda: Z.lees_account_alles("/marketplace/apps", {"type": "account_added"}, "apps", 2))


def test_a12_a15_gate_en_herpoging_in_dezelfde_week():
    basis = "# Proef\n\n## Accountscan\n\nACCOUNTSCAN: aan\n\n## Wat ik doe\n\nProef"
    assert ZA.scan_aan(basis)
    for tekst in (basis.replace("ACCOUNTSCAN: aan", "ACCOUNTSCAN: uit"), basis.replace("ACCOUNTSCAN: aan", " ACCOUNTSCAN: aan"),
                  basis.replace("ACCOUNTSCAN: aan", "ACCOUNTSCAN: aan\nACCOUNTSCAN: aan"),
                  basis.replace("## Accountscan", "## Anders")):
        assert not ZA.scan_aan(tekst)
    assert ZA.aan_de_beurt({}, KLOK)
    assert ZA.aan_de_beurt({"laatste_volledig": "2026-W43"}, KLOK)
    assert not ZA.aan_de_beurt({"laatste_volledig": "2026-W44"}, KLOK)


def test_a18_brusselse_iso_week_aan_de_wintertijd():
    assert ZA.week_van(datetime(2026, 10, 24, 21, 30, tzinfo=timezone.utc)) == "2026-W43"
    assert ZA.week_van(datetime(2026, 10, 25, 23, 30, tzinfo=timezone.utc)) == "2026-W44"


def test_a20_a21_a22_opslag_parser_geen_dubbele_telling_en_band():
    u = {"plan_base": {"type": "monthly", "hosts": 4},
         "plan_recording": {"free_storage": "10 GB", "free_storage_usage": "8.8 GB",
                            "plan_storage": "0", "plan_storage_usage": "8.8 GB"}}
    trend = [{"date": "2026-10-21", "usage": "7.3 GB"}, {"date": "2026-10-26", "usage": "8.8 GB"}]
    s = ZA.opslag(u, trend, KLOK)
    assert s["pct"] == 88 and s["gebruikt_gb"] == 8.8 and s["vol_dagen"] == 4
    assert ZA.opslag({**u, "plan_recording": {"free_storage_usage": "veel"}})["stand"].startswith("onbekend")
    d = proefstand()
    a = next(x for x in ZA.adviezen(d) if x["code"] == "ZA-01")
    assert a["toestand"] == "open" and a["ernst"] == "hoog" and a["stand"]["band"] == 80
    d["account"]["recording.auto_delete_cmr"] = True
    assert next(x for x in ZA.adviezen(d) if x["code"] == "ZA-01")["toestand"] == "goed"


def test_a23_a25_a26_adviezen_steunen_alleen_op_bekende_velden():
    d = proefstand()
    a = {x["code"]: x for x in ZA.adviezen(d, 5)}
    assert a["ZA-02"]["toestand"] == "open" and "vangnet" in a["ZA-02"]["reden"]
    assert a["ZA-04"]["toestand"] == "open" and a["ZA-04"]["ernst"] == "hoog"
    assert a["ZA-05"]["toestand"] == "goed"
    d["locks"].update({"wachtkamer": False, "toegangscode": True})
    d["meeting_security"]["meeting_security.meeting_password"] = False
    a5 = next(x for x in ZA.adviezen(d) if x["code"] == "ZA-05")
    assert a5["toestand"] == "open" and a5["ernst"] == "laag"
    assert "pakket" in a5["reden"] and "onbeschermde" not in a5["reden"]
    d["locks"].pop("wachtkamer")
    assert next(x for x in ZA.adviezen(d) if x["code"] == "ZA-05")["toestand"] == "onbekend"
    d["security"]["tweestaps"] = "group"
    assert next(x for x in ZA.adviezen(d) if x["code"] == "ZA-04")["toestand"] == "onbekend"
    d["ruimte"].update({"wachtkamer": False, "toegangscode": True, "voor_host": True})
    a6 = next(x for x in ZA.adviezen(d) if x["code"] == "ZA-06")
    assert a6["toestand"] == "open" and a6["stand"]["code"] is True


def test_j10_facebook_leest_het_gemeten_securityveld():
    d = proefstand()
    d["security"] = ZA.beveiliging({"sign_in_with_two_factor_auth": "none", "sign_in_with_fb": True,
                                     "sign_in_with_sms_code": True})
    assert d["security"]["facebook"] is True
    assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-15")["toestand"] == "open"
    d["gebruikers"] = ZA.gebruikers([{"type": 2}])
    assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-15")["toestand"] == "onbekend"


def test_a28_a29_a38_eigen_app_naam_en_tekstveld_verdwijnen():
    bron = {"schedule_meeting": {"pmi_password": "a1B2c3", "meeting_name": "Voornaam"},
            "recording": {"cloud_recording": True}, "profile": {"recording_storage_location":
            {"value": "US", "allowed_values": ["US", "DE"]}}}
    veilig = ZA.instellingen(bron)
    assert "a1B2c3" not in json.dumps(veilig) and "Voornaam" not in json.dumps(veilig)
    assert veilig["landen"] == ["DE", "US"]
    rows = [{"app_id": "abcdef", "app_name": "Eigen Voornaam", "app_status": "UNPUBLISHED"},
            {"app_id": "ghijkl", "app_name": "Verzonnen Agenda", "app_status": "PUBLISHED"}]
    details = {"abcdef": {"app_scopes": [{"scope_name": "user:write:profile:admin"}] * 5},
               "ghijkl": {"app_scopes": [{"scope_name": "user:write:profile:admin"}]}}
    a = ZA.apps(rows, details)
    assert "Voornaam" not in json.dumps(a) and a["overzicht"][0]["naam"] in ("eigen app", "externe app")
    assert a["eigen"] == 1


def test_a30_a31_m1_cyclus_na_goed_en_zelfde_open_stand():
    d = proefstand()
    staat = {}
    a = next(x for x in ZA.adviezen(d, staat_acc=staat) if x["code"] == "ZA-04")
    assert a["cyclus"] == 0
    d["security"]["tweestaps"] = "all"
    assert next(x for x in ZA.adviezen(d, staat_acc=staat) if x["code"] == "ZA-04")["toestand"] == "goed"
    d["security"]["tweestaps"] = "none"
    a = next(x for x in ZA.adviezen(d, staat_acc=staat) if x["code"] == "ZA-04")
    assert a["cyclus"] == 1
    assert ZA.voorstel_van(a, ZA.week_van(KLOK))["parameters"]["cyclus"] == 1


def test_a33_m8_weekplafond_hoog_altijd_en_hoog_laatst():
    d = proefstand()
    adv = ZA.adviezen(d)
    gekozen, wachtrij = ZA.te_versturen(adv, [], KLOK)
    assert len(gekozen) == 3 and {a["code"] for a in gekozen} == {"ZA-01", "ZA-02", "ZA-04"}
    assert sum(a["toestand"] == "open" for a in adv) == 11 and len(wachtrij) == 8
    assert [a["code"] for a in gekozen[-2:]] == ["ZA-01", "ZA-04"]
    r = {"parameters": json.dumps({"zoom_advies": "ZA-99"}), "ts": "2026-10-26T06:00:00+00:00"}
    gekozen, _ = ZA.te_versturen(adv, [r, r, r], KLOK)
    assert all(a["ernst"] == "hoog" for a in gekozen) and len(gekozen) == 2 and wachtrij


def test_a36_a37_a38_week_en_gebruik_zonder_privevelden():
    d = proefstand()
    adv = ZA.adviezen(d)
    w = ZA.weekoverzicht(d, adv, [], ZA.week_van(KLOK), KLOK, True)
    g = ZA.gebruiksmelding(d, ZA.week_van(KLOK), KLOK)
    assert w["soort"] == "zoom-account" and w["sleutel"] == "" and "datum" not in w["inhoud"]
    assert g["soort"] == "gebruik" and g["sleutel"] == "account" and "onbekend" in g["inhoud"]["facturen"]
    for item in (w, g):
        assert "@" not in json.dumps(item) and "9100000001" not in json.dumps(item)
    for slecht in ({"extra": "x"}, {"titel": "voornaam@voorbeeld.test"}, {"titel": "9100000001"},
                   {"inhoud": {"topic": "Proef"}}):
        _weigert(lambda slecht=slecht: ZA.schoon(slecht))
    ZA.schoon({"titel": "Gemeten 2026-10-26T07:04:12+00:00; code abcdefghijklmnop"})


def test_a40_a41_a46_herhaling_krijgt_nieuwe_uniek_en_basis_schuift_niet():
    d = proefstand()
    oud = ZA.basis_van(d)
    d["account"]["in_meeting.waiting_room"] = False
    nieuw = ZA.basis_van(d)
    v = ZA.verschil(oud, nieuw)
    m1 = ZA.wijzigingsmelding(v, oud, ZA.week_van(KLOK), KLOK)
    assert len(v["instellingen"]) == 1 and m1["soort"] == "zoom-account"
    omgekeerd = ZA.verschil(nieuw, oud)
    assert ZA.wijzigingsmelding(omgekeerd, nieuw, ZA.week_van(KLOK), KLOK)["uniek"] != m1["uniek"]
    assert ZA.wijzigingsmelding(v, oud, ZA.week_van(KLOK), KLOK)["uniek"] == m1["uniek"]
    # A -> B -> A -> B: dezelfde basis en hetzelfde verschil, maar de derde
    # bevestigde melding moet een nieuw bord-id krijgen. Een herpoging niet.
    eerste = ZA.wijzigingsmelding(v, oud, ZA.week_van(KLOK), KLOK, 1)
    derde = ZA.wijzigingsmelding(v, oud, ZA.week_van(KLOK), KLOK, 3)
    assert eerste["uniek"] != derde["uniek"]
    assert ZA.wijzigingsmelding(v, oud, ZA.week_van(KLOK), KLOK, 3)["uniek"] == derde["uniek"]


def test_a44_logboek_telt_twee_handeling_in_dezelfde_seconde():
    rij = {"time": "2026-10-26T07:00:00Z", "category_type": "Role", "action": "Update User Role",
           "operator": "persoon@voorbeeld.test", "operation_detail": "geheim"}
    a = ZA.beheerlogboek([rij, rij])
    assert a["aantal"] == 2 and list(a["gevoelig"].values()) == [2]
    assert "@" not in json.dumps(a) and "geheim" not in json.dumps(a)
    assert ZA.verschil({"beheerlogboek": {}}, {"beheerlogboek": a["gevoelig"], "apps": {}})["beheerhandelingen"] == 2


def test_j13_apprechten_alleen_na_weekdetail_in_overzicht():
    d = proefstand()
    vorige = ZA.basis_van(d)
    assert ZA.apprechten_veranderd(None, d["apps"])["stand"].startswith("onbekend")
    d["apps"]["overzicht"][0]["schrijf"] = 8
    d["app_rechten"] = ZA.apprechten_veranderd(vorige, d["apps"])
    assert d["app_rechten"]["overzicht"] == [{"naam": "externe app", "rechten_van": 10,
                                             "rechten_naar": 10, "schrijf_van": 6, "schrijf_naar": 8}]
    inhoud = ZA.weekoverzicht(d, [], [], ZA.week_van(KLOK), KLOK, True)["inhoud"]
    assert inhoud["apps"]["rechten_veranderd"] == d["app_rechten"]["overzicht"]


def test_a12_grens_uit_geeft_nul_accountvragen():
    class R:
        werkwijze = "# Proef\n\n## Accountscan\n\nACCOUNTSCAN: uit"
    with patch.object(ZA, "lees_week", side_effect=AssertionError("accountvraag")):
        assert ZA.ronde(R(), {"identiteit_ok": True, "ik": {"id": "vast", "pmi": "9100000001"}}, {}, KLOK) == ""


def test_a19_droog_alleen_codes_en_tellingen():
    d = proefstand()
    b = io.StringIO()
    with patch.object(ZA.Z, "leesapp", return_value=True), patch.object(ZA.Z, "leesapp_fout", return_value=""), \
         patch.object(ZA.Z, "leesapp_verboden", return_value=[]), \
         patch.object(ZA, "lees_week", return_value=(d, [], True, 25)), redirect_stdout(b):
        ZA.droog({"identiteit_ok": True, "ik": {"id": "vast", "pmi": "9100000001"}}, KLOK)
    assert "ZA-01" in b.getvalue() and "@" not in b.getvalue()


def gemeten_antwoorden():
    return {
        "/accounts/me/settings": {"recording": {"auto_delete_cmr": False, "cloud_recording": True,
                                                    "record_speaker_view": True, "record_gallery_view": False,
                                                    "record_files_separately": {"active_speaker": False,
                                                                                "gallery_view": True, "shared_screen": False}},
                                  "in_meeting": {"waiting_room": True}},
        "/accounts/me/lock_settings": {"in_meeting": {"waiting_room": False},
                                       "meeting_security": {"meeting_password": True}},
        "/users/vaste-id/settings": {"recording": {"auto_recording": "cloud", "recording_audio_transcript": True,
                                                     "record_audio_file": False, "record_speaker_view": True,
                                                     "record_gallery_view": False,
                                                     "record_files_separately": {"active_speaker": False,
                                                                                 "gallery_view": False, "shared_screen": True}},
                                     "schedule_meeting": {"require_password_for_pmi_meetings": "none"}},
        "/meetings/9100000001": {"type": 2, "settings": {"waiting_room": True,
                                                            "join_before_host": False,
                                                            "auto_recording": "none"}},
        "/roles": {"roles": [{"id": "owner", "name": "Owner", "total_members": 1}]},
        "/groups": {"groups": [{"total_members": 0}]},
        "/users": {"users": [{"type": 2, "login_types": [0]}]},
        "/users/summary": {"licensed_users_count": 4, "basic_users_count": 7,
                           "room_users_count": 0, "pending_users_count": 1,
                           "on_prem_users_count": 0, "join_only_users_count": 0},
        "/accounts/me/plans": {"plan_base": {"type": "yearly", "hosts": 1}},
        "/accounts/me/plans/usage": {"plan_base": {"type": "yearly", "hosts": 1},
                                      "plan_recording": {"free_storage": "10 GB", "free_storage_usage": "8.8 GB", "plan_storage": "0"}},
        "/report/cloud_recording": {"cloud_recording_storage": [
            {"date": "2026-10-21", "usage": "7.3 GB"}, {"date": "2026-10-26", "usage": "8.8 GB"}]},
        "/accounts/me/recordings": {"meetings": [{"start_time": "2026-10-24T07:00:00Z", "duration": 20,
                                                    "recording_files": [{"file_type": "MP4", "file_size": 9000000},
                                                                        {"file_type": "M4A", "file_size": 1000000}]}]},
        "/meetings/meeting_summaries": {"summaries": []},
        "/report/activities": {"activity_logs": []},
        "/report/operationlogs": {"operation_logs": []},
        "/report/users": {"users": []},
        "/report/daily": {"dates": [{"meetings": 1, "participants": 2, "meeting_minutes": 10, "new_users": 0}]},
        "/accounts/me/billing/invoices": {"invoices": []},
        "/marketplace/apps": {"apps": [{"app_id": "abcdef", "app_name": "Voorbeeld Planner",
                                         "app_status": "PUBLISHED"}]},
        # Gemeten vorm (22-10): app_scopes als lijst tekstregels.
        "/marketplace/apps/abcdef": {"app_scopes": ["zoomapp:inmeeting", "meeting:write", "imchat:bot"]},
    }


def test_a07_a08_a09_weeklezer_vraagt_alle_delen_en_houdt_onbekend_apart():
    ant = gemeten_antwoorden()
    def lees(pad, params=None):
        if pad == "/accounts/me/settings" and params:
            return {"sign_in_with_two_factor_auth": "none"} if params.get("option") == "security" else \
                {"meeting_security": {"meeting_password": False}} if params.get("option") == "meeting_security" else {}
        return ant[pad]
    with patch.object(Z, "lees_account", side_effect=lees), patch.object(ZA.time, "sleep", return_value=None), \
         patch.object(Z, "PAUZE", 0):
        d, fouten, volledig, vragen = ZA.lees_week("vaste-id", "9100000001", KLOK)
    assert volledig and all(x[1] == "facturen" for x in fouten) and vragen >= 20, (fouten, vragen)
    assert d["facturen"]["stand"].startswith("onbekend") and d["apps"]["aantal"] == 1
    assert d["opslag"]["pct"] == 88 and d["samenvatting"]["licensed"] == 4
    assert d["meeting_security"]["meeting_security.meeting_password"] is False
    assert d["apps"]["aantal"] == 1 and d["apps"]["overzicht"][0]["schrijf"] == 1
    assert d["user"]["recording.record_files_separately.shared_screen"] is True
    adv = {a["code"]: a for a in ZA.adviezen(d)}
    assert adv["ZA-01"]["toestand"] == "open" and adv["ZA-01"]["ernst"] == "hoog"
    assert adv["ZA-04"]["toestand"] == "open" and adv["ZA-04"]["ernst"] == "hoog"
    assert adv["ZA-02"]["toestand"] == "open"
    assert adv["ZA-05"]["toestand"] == "open" and adv["ZA-05"]["ernst"] == "laag"
    ant["/accounts/me/plans/usage"] = {"plan_recording": {"free_storage": "onbekend"}}
    with patch.object(Z, "lees_account", side_effect=lees), patch.object(ZA.time, "sleep", return_value=None), \
         patch.object(Z, "PAUZE", 0):
        d, fouten, volledig, _ = ZA.lees_week("vaste-id", "9100000001", KLOK)
    assert d["opslag"]["stand"].startswith("onbekend") and \
        next(x for x in ZA.adviezen(d) if x["code"] == "ZA-01")["toestand"] == "onbekend"


def test_a15_a30_a35_a36_ronde_bewaart_week_pas_na_bordbewijs():
    d = proefstand()
    rows, items, noden = [], [], []
    class Agent:
        def __init__(self, naam):
            self.naam = naam
        def hartslag(self, status, taak="", voorstel=None, **_):
            if voorstel:
                rows.append({"id": len(rows) + 1, "actie": voorstel["actie"],
                             "parameters": json.dumps(voorstel["parameters"]), "status": "open",
                             "ts": KLOK.isoformat()})
        def klaarzet(self, nieuw):
            items.extend(nieuw)
            return {"nieuw": len(nieuw)}
        def log(self, *_):
            pass
    class R:
        werkwijze = "# Proef\n\n## Accountscan\n\nACCOUNTSCAN: aan\n"
        agent = Agent("zoom-wacht")
        def nood(self, tekst, wie="mehdi"):
            noden.append((tekst, wie))
        def bron(self, *_):
            pass
    staat = {}
    w = {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}}
    with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
         patch.object(Z, "leesapp_verboden", return_value=[]), patch.object(ZA, "lees_week", return_value=(d, [], True, 25)), \
         patch.object(ZA, "voorstellen_lezen", side_effect=lambda: rows), patch.object(ZA.bord, "Agent", Agent):
        ZA.ronde(R(), w, staat, KLOK, 5)
    assert staat["account"]["laatste_volledig"] == "2026-W44"
    assert len(rows) == 3 and len(items) == 2 and not noden
    assert items[0]["soort"] == "zoom-account" and items[1]["soort"] == "gebruik"
    assert all("@" not in json.dumps(x) for x in items)
    zonder_bord = {}
    with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
         patch.object(Z, "leesapp_verboden", return_value=[]), patch.object(ZA, "lees_week", return_value=(d, [], True, 25)), \
         patch.object(ZA, "voorstellen_lezen", side_effect=ZA.bord.BordOnbekend("proef")), \
         patch.object(ZA.bord, "Agent", Agent):
        ZA.ronde(R(), w, zonder_bord, KLOK, 5)
    assert "laatste_volledig" not in zonder_bord["account"]
    assert any("Zoom-advies niet terug te lezen" in n for n, _ in noden)


def test_a38_witte_lijst_bewaakt_elk_uitgaand_soort():
    d = proefstand()
    adv = ZA.adviezen(d)
    voorstel = ZA.voorstel_van(next(a for a in adv if a["code"] == "ZA-04"), ZA.week_van(KLOK))
    week = ZA.weekoverzicht(d, adv, [], ZA.week_van(KLOK), KLOK, True)
    melding = ZA.wijzigingsmelding({"instellingen": [], "apps_nieuw": [], "apps_weg": [], "beheerhandelingen": 1},
                                   {}, ZA.week_van(KLOK), KLOK)
    for item in ({"naam": "zoom-wacht", "status": "actief", "taak": "advies", "voorstel": voorstel}, week, melding):
        ZA.schoon(item)
        besmet = json.loads(json.dumps(item))
        besmet["inhoud" if "inhoud" in besmet else "voorstel"]["extra_veld"] = "x"
        _weigert(lambda besmet=besmet: ZA.schoon(besmet))


def test_a08_a24_onvolledig_detail_wordt_nooit_nul_en_verse_opname_telt_niet():
    rows = [{"app_id": "abcdef", "app_status": "PUBLISHED", "app_name": "Verzonnen Agenda"}]
    for detail in ({}, {"app_scopes": [{"scope_name": "View and manage your meetings"}]}):
        a = ZA.apps(rows, {"abcdef": detail})
        assert a["stand"] == "ok" and a["aantal"] == 1 and a["onbekende_rechten"] == 1
        assert a["overzicht"][0]["rechten"] is None and a["overzicht"][0]["schrijf"] is None
    assert ZA.rollen([{"name": "Owner"}])["stand"].startswith("onbekend")
    assert ZA.beheerlogboek([{"category_type": "Role"}])["stand"].startswith("onbekend")
    assert ZA.opnames([{"duration": 30, "recording_files": [{"file_type": "MP4"}]}], KLOK)["stand"].startswith("onbekend")
    rows = []
    for i in range(6):
        rows.append({"start_time": "2026-10-24T07:00:00Z" if i < 4 else "2026-10-26T06:00:00Z",
                     "duration": 30, "recording_files": [{"file_type": "MP4", "file_size": 1000000}] +
                     ([{"file_type": "TRANSCRIPT", "file_size": 1000}] if i < 4 else [])})
    rec = ZA.opnames(rows, KLOK)
    assert rec["klaar"] == 4 and rec["met_transcript"] == 4 and rec["transcript_pct"] == 100
    d = proefstand()
    d["opnames"] = rec
    assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-14")["toestand"] == "goed"


def test_a50_accountvragen_wachten_minimaal_een_halve_seconde():
    tijden = iter((0, 0, 0, 0, 0.1, 0.1, 0.1))
    wachten = []
    with patch.object(ZA.time, "monotonic", side_effect=lambda: next(tijden)), \
         patch.object(ZA.time, "sleep", side_effect=wachten.append), \
         patch.object(Z, "lees_account", return_value={}):
        l = ZA.Lezer()
        l.vraag("/users/summary")
        l.vraag("/users/summary")
    assert wachten and wachten[0] >= 0.4


def test_a10_budget_stopt_voor_een_nieuwe_zoomvraag():
    with patch.object(ZA.time, "monotonic", side_effect=(0, 241)), \
         patch.object(Z, "lees_account", side_effect=AssertionError("geen vraag na budget")):
        l = ZA.Lezer(240)
        try:
            l.vraag("/users/summary")
        except ZA.ScanFout as e:
            assert str(e) == "tijd op" and l.vragen == 0
        else:
            raise AssertionError("budget niet afgedwongen")


def test_a53_vol_opslag_geeft_nood_en_daarna_niet():
    noden = []
    class R:
        def nood(self, tekst, wie):
            noden.append((tekst, wie))
    ZA._noden(R(), [], True, {"pct": 100})
    assert any("Zoom-cloudopslag vol" in n for n, _ in noden)
    noden.clear()
    ZA._noden(R(), [], True, {"pct": 95})
    assert not noden


def test_a16_a45_a52_herpoging_en_nood_na_twee_foute_wijzigingen():
    d = proefstand()
    d["pakket"]["hosts"] = 2
    class Agent:
        def __init__(self, naam):
            self.naam = naam
        def klaarzet(self, items):
            return {"nieuw": len(items)}
        def log(self, *_):
            pass
    class R:
        werkwijze = "# Proef\n\n## Accountscan\n\nACCOUNTSCAN: aan\n"
        agent = Agent("zoom-wacht")
        def __init__(self):
            self.noden = []
        def nood(self, tekst, wie="mehdi"):
            self.noden.append(tekst)
        def bron(self, *_):
            pass
    staat = {"account": {"pakket": {"periode": "yearly", "hosts": 1}}}
    w = {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}}
    antwoorden = iter(((d, [("beveiliging", "security", "HTTP 400")], False, 4), (d, [], True, 25)))
    with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
         patch.object(Z, "leesapp_verboden", return_value=[]), patch.object(ZA, "lees_week", side_effect=lambda *a: next(antwoorden)), \
         patch.object(ZA, "voorstellen_lezen", return_value=[]), patch.object(ZA, "te_versturen", return_value=([], [])), \
         patch.object(ZA.bord, "Agent", Agent):
        r1 = R()
        ZA.ronde(r1, w, staat, KLOK)
        assert "laatste_volledig" not in staat["account"] and any("nog niet gelukt" in x for x in r1.noden)
        assert "Zoom-pakket veranderd: het dashboard opnieuw meten" in r1.noden
        r2 = R()
        ZA.ronde(r2, w, staat, KLOK.replace(hour=13))
        assert staat["account"]["laatste_volledig"] == "2026-W44"
    fouten = iter((({}, [("apps", "apps", "HTTP 400")], 1), ({}, [("apps", "apps", "HTTP 400")], 1), (d, [], 5)))
    with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
         patch.object(Z, "leesapp_verboden", return_value=[]), patch.object(ZA, "lees_wijziging", side_effect=lambda *a: next(fouten)), \
         patch.object(ZA, "voorstellen_lezen", return_value=[]), patch.object(ZA.bord, "Agent", Agent):
        r1, r2, r3 = R(), R(), R()
        ZA.ronde(r1, w, staat, KLOK.replace(hour=14))
        ZA.ronde(r2, w, staat, KLOK.replace(hour=15))
        ZA.ronde(r3, w, staat, KLOK.replace(hour=16))
    assert not r1.noden and "Zoom-wijzigingscontrole twee rondes na elkaar niet gelezen" in r2.noden
    assert not r3.noden and staat["account"]["wijziging_fouten"] == 0


def test_za2_klassieke_apprechten_met_twee_delen_en_stabiele_band():
    detail = {"app_scopes": [{"scope_name": x} for x in (
        "zoomapp:inmeeting", "imchat:bot", "meeting:write", "user:read", "chat_message:update")]}
    assert ZA._rechten_detail(detail) == (5, 2)
    rows = [{"app_id": "proefaaa", "app_name": "Iemand Proef", "app_status": "PUBLISHED"},
            {"app_id": "proefbbb", "app_name": "Andere Proef", "app_status": "PUBLISHED"}]
    basis = {r["app_id"]: {"app_scopes": [{"scope_name": "meeting:write"},
                                           {"scope_name": "user:write"}, {"scope_name": "chat:write"},
                                           {"scope_name": "report:write"}, {"scope_name": "recording:write"}]}
             for r in rows}
    d = proefstand()
    d["apps"] = ZA.apps(rows, basis)
    a = next(x for x in ZA.adviezen(d) if x["code"] == "ZA-10")
    assert a["toestand"] == "open" and set(a["stand"]["banden"]) == {5}
    basis["proefbbb"]["app_scopes"] += [{"scope_name": "meeting:update"}, {"scope_name": "user:update"}]
    d["apps"] = ZA.apps(rows, basis)
    b = next(x for x in ZA.adviezen(d) if x["code"] == "ZA-10")
    assert b["stand"] == a["stand"], "getallen binnen dezelfde band mogen geen nieuw voorstel maken"


def test_za2_licenties_lezen_gemeten_sleutelnamen():
    bron = {f"{k}_users_count": n for k, n in (("licensed", 4), ("basic", 7), ("room", 0),
                                                ("pending", 1), ("on_prem", 0), ("join_only", 0))}
    assert ZA.gebruikers_samenvatting(bron)["licensed"] == 4
    assert ZA.gebruikers_samenvatting(bron)["pending"] == 1
    bron.pop("licensed_users_count")
    assert ZA.gebruikers_samenvatting(bron)["stand"].startswith("onbekend")


def test_za2_vol_plan_recording_geeft_opslagnood():
    opslag = ZA.opslag({"plan_recording": {"free_storage": "10 GB", "plan_storage": "0",
                                                 "free_storage_usage": "10 GB"}})
    noden = []
    ZA._noden(type("R", (), {"nood": lambda self, tekst, wie: noden.append((tekst, wie))})(),
              [], True, opslag)
    assert opslag["pct"] == 100 and noden == [
        ("Zoom-cloudopslag vol: het vangnet kan geen Zoom-tekst meer halen", "mehdi")]


def test_za2_meetingbeveiliging_is_al_genest():
    def lees(pad, params=None):
        if pad == "/accounts/me/settings" and params == {"option": "meeting_security"}:
            return {"meeting_security": {"meeting_password": False, "pmi_password": True}}
        return {}
    with patch.object(Z, "lees_account", side_effect=lees), patch.object(ZA.time, "sleep", return_value=None), \
         patch.object(Z, "PAUZE", 0):
        d, _, _, _ = ZA.lees_week("vaste-id", "9100000001", KLOK)
    assert d["meeting_security"]["meeting_security.meeting_password"] is False
    assert d["meeting_security"]["meeting_security.pmi_password"] is True


def test_za2_za10_stand_sorteert_op_appcode_bij_gelijke_band():
    d = proefstand()
    d["apps"]["met_schrijfrechten"] = [
        {"code": "bbbbbbbbbbbbbbbb", "naam": "externe app", "schrijf": 11},
        {"code": "aaaaaaaaaaaaaaaa", "naam": "externe app", "schrijf": 10}]
    voor = next(a for a in ZA.adviezen(d) if a["code"] == "ZA-10")["stand"]
    d["apps"]["met_schrijfrechten"] = [
        {"code": "aaaaaaaaaaaaaaaa", "naam": "externe app", "schrijf": 12},
        {"code": "bbbbbbbbbbbbbbbb", "naam": "externe app", "schrijf": 10}]
    na = next(a for a in ZA.adviezen(d) if a["code"] == "ZA-10")["stand"]
    assert voor == na == {"apps": ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"], "banden": [10, 10]}


def test_za2_za12_gebruikt_inactiviteit_en_niet_periodiek_afmelden():
    bron = {"sign_in_with_two_factor_auth": "all", "sign_again_period_for_inactivity_on_client": 0,
            "sign_again_period_for_inactivity_on_web": 30,
            "automatic_sign_out": {"email_or_phone": {"desktop_client": 90, "mobile_client": 90,
                                                        "web_browser": 90, "zoom_scheduling_integration": -1}}}
    assert ZA.beveiliging(bron)["afmelden"] == "uit"
    d = proefstand()
    d["security"] = ZA.beveiliging(bron)
    assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-12")["toestand"] == "open"
    bron["sign_again_period_for_inactivity_on_client"] = 20
    assert ZA.beveiliging(bron)["afmelden"] == "aan"
    bron.pop("sign_again_period_for_inactivity_on_client")
    assert ZA.beveiliging(bron)["afmelden"] is None


def test_za2_za02_eist_alle_video_opties_en_za04_noemt_aanmeldvoorwaarde():
    d = proefstand()
    assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-02")["toestand"] == "open"
    d["user"].pop("recording.record_files_separately.shared_screen")
    assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-02")["toestand"] == "onbekend"
    a4 = next(a for a in ZA.adviezen(d) if a["code"] == "ZA-04")
    tekst = ZA.voorstel_van(a4, ZA.week_van(KLOK))["reden"]
    assert "werk-e-mail" in tekst and "Google of SSO" in tekst


def test_za2_nagekeken_klikpaden_en_supportticket():
    p = ZA.KLIKPADEN
    for code, stuk in (("ZA-01", "Recording & Transcript"), ("ZA-03", "Create audio transcript"),
                       ("ZA-04", "two-step verification"), ("ZA-05", "Enable waiting room"),
                       ("ZA-06", "Personal Room"), ("ZA-07", "Recordings and content location"),
                       ("ZA-09", "Auto-delete meeting summaries"), ("ZA-11", "User Management > Groups"),
                       ("ZA-12", "Users need to sign in again after a period of inactivity"),
                       ("ZA-14", "Recording and Transcript Management > Recordings")):
        assert stuk in p[code] and not p[code].startswith("Admin > Advanced")
    assert "Admin App Management > Apps on Account" in p["ZA-10"]
    assert p["ZA-08"] == ""
    d = proefstand()
    for code in ("ZA-02", "ZA-10", "ZA-13"):
        a = next(a for a in ZA.adviezen(d) if a["code"] == code)
        tekst = ZA.voorstel_van(a, ZA.week_van(KLOK))["reden"]
        assert "te bevestigen" in tekst and "Controleer de werking" in tekst
        assert tekst.endswith("Weigeren: ik vraag het bij dezelfde stand niet opnieuw.")
    a8 = next(a for a in ZA.adviezen(d) if a["code"] == "ZA-08")
    tekst = ZA.voorstel_van(a8, ZA.week_van(KLOK))["reden"]
    assert "Zoom Support" in tekst and "ticket" in tekst and "Klikpad" not in tekst


def test_za2_onbekende_bronnen_blijven_onbekend_en_geven_geen_nul():
    d = {"opslag": {"stand": "onbekend: opslag ontbreekt"},
         "samenvatting": {"stand": "onbekend: telling ontbreekt"}}
    w = ZA.weekoverzicht(d, ZA.adviezen(d), [], ZA.week_van(KLOK), KLOK, False)["inhoud"]
    g = ZA.gebruiksmelding(d, ZA.week_van(KLOK), KLOK)["inhoud"]
    assert w["opnames"]["opslag"]["gebruikt_gb"].startswith("onbekend")
    assert w["licenties"]["licensed"].startswith("onbekend")
    assert g["opslag"]["gebruikt_gb"].startswith("onbekend")
    assert g["licenties"]["licensed"].startswith("onbekend")
    noden = []
    ZA._noden(type("R", (), {"nood": lambda self, tekst, wie: noden.append((tekst, wie))})(), [], True, None)
    assert not noden


def test_za2_privacygrendel_weigert_telefoon_ipv6_en_vanitylink():
    for waarde in ("+32 4 123 45 67", "0470 12 34 56", "2001:db8::cafe", "::1", "zoom.us/my-proef"):
        _weigert(lambda waarde=waarde: ZA.schoon({"titel": waarde}))


def test_za2_privacy_vrije_zoomvelden_tot_en_met_bord_staat_en_export():
    privé = ("Ada Voorbeeld", "ada@voorbeeld.test", "+32 4 123 45 67",
             "2001:db8::cafe", "zoom.us/my-proef")
    vuil = " | ".join(privé)
    d = proefstand()
    d["account"]["display_name"] = vuil
    d["security"]["free_text"] = vuil
    d["user"]["job_title"] = vuil
    d["ruimte"] = ZA.ruimte({"topic": vuil, "join_url": vuil,
                             "settings": {"waiting_room": True, "join_before_host": False,
                                          "auto_recording": "none", "description": vuil}})
    d["gebruikers"] = ZA.gebruikers([{"type": 2, "login_types": [1], "display_name": vuil,
                                     "email": vuil, "phone": vuil, "role_id": vuil}])
    d["opnames"] = ZA.opnames([{"start_time": "2026-10-24T07:00:00Z", "duration": 20,
                               "topic": vuil, "share_url": vuil,
                               "recording_files": [{"file_type": "MP4", "file_size": 9000000,
                                                    "download_url": vuil, "play_url": vuil}]}], KLOK)
    d["apps"] = ZA.apps([{"app_id": "abcdef", "app_name": vuil, "app_status": "PUBLISHED",
                          "description": vuil}], {"abcdef": {"app_scopes": [{"scope_name": "meeting:write"}]}})
    d["logboek"] = ZA.beheerlogboek([{"time": "2026-10-24T07:00:00Z", "category_type": "User",
                                     "action": "Ada Voorbeeld", "operator": vuil, "operation_detail": vuil}])
    d["activiteiten"] = ZA.activiteiten([{"action": "login", "user_name": vuil, "ip_address": vuil}])
    d["rollen"]["beheer_ids"]["Member"] = vuil
    d["groepen"]["name"] = vuil
    d["pakket"]["account_name"] = vuil
    d["samenvattingen"]["topic"] = vuil
    d["rapport_actief"]["email"] = vuil
    d["daggebruik"]["description"] = vuil
    for bron in d.values():
        if isinstance(bron, dict):
            bron.update({"name": vuil, "email": vuil, "phone": vuil, "ip_address": vuil,
                         "topic": vuil, "share_url": vuil, "zoom_link": vuil})
    voorstellen, items, noden, bronnen, logs = [], [], [], [], []
    class Agent:
        def __init__(self, naam):
            self.naam = naam
        def hartslag(self, status, taak="", voorstel=None, **_):
            if voorstel:
                voorstellen.append({"id": len(voorstellen) + 1, "naam": "zoom-wacht", "status": "open",
                                   **voorstel, "ts": KLOK.isoformat()})
        def klaarzet(self, nieuwe):
            items.extend(nieuwe)
            return {"nieuw": len(nieuwe)}
        def log(self, onderwerp, stap, tekst, detail=""):
            logs.append({"naam": "zoom-wacht", "onderwerp": onderwerp, "stap": stap,
                         "tekst": tekst, "detail": detail, "ts": KLOK.isoformat()})
    class R:
        werkwijze = "# Proef\n\n## Accountscan\n\nACCOUNTSCAN: aan\n"
        agent = Agent("zoom-wacht")
        def nood(self, tekst, wie="mehdi"):
            noden.append({"naam": "zoom-wacht", "tekst": tekst, "wie": wie,
                          "open": 1, "ts": KLOK.isoformat(), "opgelost_ts": ""})
        def bron(self, naam, inhoud):
            bronnen.append((naam, inhoud))
    staat = {}
    with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
         patch.object(Z, "leesapp_verboden", return_value=[]), \
         patch.object(ZA, "lees_week", return_value=(d, [], True, 24)), \
         patch.object(ZA, "voorstellen_lezen", side_effect=lambda: [
             {"id": x["id"], "actie": x["actie"], "parameters": json.dumps(x["parameters"]),
              "status": "open", "ts": x["ts"]} for x in voorstellen]), \
         patch.object(ZA.bord, "Agent", Agent):
        ZA.ronde(R(), {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}},
                 staat, KLOK, 2)
    samen = json.dumps((voorstellen, items, noden, bronnen, logs, staat), ensure_ascii=False)
    assert all(x not in samen for x in privé)
    assert voorstellen and items and bronnen and logs and staat["account"]["basis"]

    spec = importlib.util.spec_from_file_location("bord_export_proef", os.path.join(os.path.dirname(HIER), "bord_export.py"))
    export = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export)
    tijd = KLOK.isoformat()
    klaar = [{"van": "zoom-wacht", "voor": x["voor"], "soort": x["soort"], "sleutel": x["sleutel"],
              "titel": x["titel"], "inhoud": json.dumps(x["inhoud"]), "verwijzing": "", "status": "nieuw", "ts": tijd}
             for x in items]
    vs = [{"naam": "zoom-wacht", "actie": x["actie"], "doel": x["doel"], "reden": x["reden"],
           "parameters": json.dumps(x["parameters"]), "runbook": "", "status": "open",
           "besluit_door": "", "ts": tijd} for x in voorstellen]
    class FakeDb:
        row_factory = None
        def execute(self, query, args=()):
            if "select titel, inhoud, verwijzing from klaarzet" in query:
                return klaar
            if "from agent" in query and "join" not in query:
                return [{"naam": "zoom-wacht", "label": "De Zoomwacht", "type": "VM", "rol": "proef",
                         "cadans": "week", "werkwijze": R.werkwijze, "actief": 1}]
            if "from logboek" in query:
                return logs
            if "from klaarzet" in query and "select van, voor" in query:
                return klaar
            if "from nood" in query:
                return noden
            if "from voorstel" in query:
                return vs
            if "from status s" in query:
                return [{"naam": "zoom-wacht", "label": "De Zoomwacht", "status": "klaar",
                         "taak": "Zoom-account", "detail": "scan voltooid", "ts": tijd}]
            return []
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tijdelijk:
        export.DATA, export.UIT = tijdelijk, os.path.join(tijdelijk, "export")
        with patch.object(export.sqlite3, "connect", return_value=FakeDb()), redirect_stdout(io.StringIO()):
            export.main()
        teksten = []
        for wortel, _, namen in os.walk(export.UIT):
            for naam in namen:
                with open(os.path.join(wortel, naam), encoding="utf-8") as f:
                    teksten.append(f.read())
        assert teksten and all(x not in "\n".join(teksten) for x in privé)


def test_za2_gemist_recht_wordt_nood_met_rechtnaam():
    noden = []
    class R:
        def nood(self, tekst, wie):
            noden.append((tekst, wie))
    ZA._noden(R(), [("beveiliging", "logboek", "geen recht report:read:operation_logs:admin")],
              False, None)
    assert any(wie == "mehdi" and "report:read:operation_logs:admin" in tekst for tekst, wie in noden)


def test_za2_maximaal_een_wijzigingsmelding_per_brusselse_dag():
    basis = proefstand()
    eerste = proefstand()
    eerste["account"]["in_meeting.waiting_room"] = False
    tweede = proefstand()
    tweede["account"].update({"in_meeting.waiting_room": False, "recording.auto_delete_cmr": True})
    tweede["apps"]["overzicht"][0].update(rechten=None, schrijf=None)
    tweede["apps"]["met_schrijfrechten"] = []
    tweede["apps"]["onbekende_rechten"] = 1
    items = []
    class Agent:
        def __init__(self, naam):
            pass
        def klaarzet(self, nieuw):
            items.extend(nieuw)
            return {"nieuw": len(nieuw)}
        def log(self, *_):
            pass
    class R:
        werkwijze = "# Proef\n\n## Accountscan\n\nACCOUNTSCAN: aan\n"
        agent = Agent("zoom-wacht")
        def nood(self, *_):
            pass
        def bron(self, *_):
            pass
    staat = {"account": {"laatste_volledig": ZA.week_van(KLOK), "basis": ZA.basis_van(basis)}}
    metingen = iter(((eerste, [], 6), (tweede, [], 6)))
    with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
         patch.object(Z, "leesapp_verboden", return_value=[]), \
         patch.object(ZA, "lees_wijziging", side_effect=lambda *a: next(metingen)), \
         patch.object(ZA.bord, "Agent", Agent):
        ZA.ronde(R(), {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}}, staat, KLOK)
        bewaarde_basis = json.loads(json.dumps(staat["account"]["basis"]))
        ZA.ronde(R(), {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}},
                 staat, KLOK.replace(hour=13))
    assert len([x for x in items if x["inhoud"]["soort"] == "wijziging"]) == 1
    assert staat["account"]["basis"] == bewaarde_basis
    code = tweede["apps"]["overzicht"][0]["code"]
    assert staat["account"]["actuele_appmeting"]["apps"][code] == {"rechten": None, "schrijf": None}
    assert staat["account"]["actuele_appmeting"]["onbekende_rechten"] == 1
    assert staat["account"]["laatst_bewezen_apprechten"][code]["rechten"] == 10


def test_za4_publieke_scopes_in_gemeten_week():
    fixture = Path(HIER, "fixtures", "zoom_leesapp_scopes.txt")
    rechten = [regel for regel in fixture.read_text().splitlines() if regel and not regel.startswith("#")]
    assert len(rechten) == len(set(rechten)) == 56
    assert "h323_device:read:list_devices:admin" in rechten
    # Gemeten vorm (22-10): app_scopes is een lijst tekstregels; de dict-vorm blijft ook leesbaar.
    detail = {"app_scopes": list(rechten)}
    assert ZA._rechten_detail(detail) == (56, 0)
    assert ZA._rechten_detail({"app_scopes": [{"scope_name": recht} for recht in rechten]}) == (56, 0)
    assert ZA._rechten_detail({"app_scopes": ["meeting:write:meeting:admin", "user:read:user:admin"]}) == (2, 1)
    # Gemeten op 22-10: OpenID-rechten naast Zoom-rechten; bekend en niet schrijvend.
    assert ZA._rechten_detail({"app_scopes": ["openid", "profile", "email", "meeting:write:meeting:admin"]}) == (4, 1)
    for vreemd in (["openid"], {"scope_name": "openid"}, None, 7):
        _weigert(lambda vreemd=vreemd: ZA._rechten_detail({"app_scopes": [{"scope_name": vreemd}]}))
    assert ZA._fout(Z.GeenRecht("h323_device:read:list_devices:admin")) == \
        "geen recht h323_device:read:list_devices:admin"
    assert ZA._fout(Z.GeenRecht("download")) == "geen recht download"
    for ongeldig in ("Meeting:Read", "meeting read", "meeting:read:extra:admin:too_long"):
        _weigert(lambda ongeldig=ongeldig: ZA._rechten_detail(
            {"app_scopes": [{"scope_name": ongeldig}]}))
    ant = gemeten_antwoorden()
    ant["/marketplace/apps/abcdef"] = detail
    def lees(pad, params=None):
        if pad == "/accounts/me/settings" and params:
            return {"sign_in_with_two_factor_auth": "none"} if params["option"] == "security" else \
                {"meeting_security": {"meeting_password": False}}
        return ant[pad]
    with patch.object(Z, "lees_account", side_effect=lees), patch.object(ZA.time, "sleep", return_value=None), \
         patch.object(Z, "PAUZE", 0):
        d, fouten, volledig, vragen = ZA.lees_week("vaste-id", "9100000001", KLOK)
    assert volledig and vragen >= 20 and all(naam == "facturen" for _, naam, _ in fouten), fouten
    assert d["apps"]["aantal"] == 1 and d["apps"]["overzicht"][0]["rechten"] == 56
    assert d["apps"]["overzicht"][0]["schrijf"] == 0
    assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-06")["toestand"] == "goed"
    assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-10")["toestand"] == "goed"


def test_za4_pmi_zonder_password_vraagt_tweede_bewijs():
    for genest in (True, False):
        ant = gemeten_antwoorden()
        instellingen = {"waiting_room": False, "join_before_host": True, "auto_recording": "none"}
        ant["/meetings/9100000001"] = {"type": 2, "settings": instellingen} if genest else \
            {"type": 2, **instellingen}
        ant["/users/vaste-id/settings"]["schedule_meeting"] = {
            "require_password_for_pmi_meetings": "none"}
        def lees(pad, params=None):
            if pad == "/accounts/me/settings" and params:
                return {"sign_in_with_two_factor_auth": "none"} if params["option"] == "security" else \
                    {"meeting_security": {"meeting_password": False}}
            return ant[pad]
        with patch.object(Z, "lees_account", side_effect=lees), patch.object(ZA.time, "sleep", return_value=None), \
             patch.object(Z, "PAUZE", 0):
            d, _, _, _ = ZA.lees_week("vaste-id", "9100000001", KLOK)
            assert d["ruimte"]["toegangscode"] is False
            assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-06")["toestand"] == "open"
            ant["/users/vaste-id/settings"]["schedule_meeting"] = {}
            d, _, _, _ = ZA.lees_week("vaste-id", "9100000001", KLOK)
            assert d["ruimte"]["toegangscode"] is None
            assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-06")["toestand"] == "onbekend"
            ruimtevelden = ant["/meetings/9100000001"]
            (ruimtevelden["settings"] if genest else ruimtevelden)["waiting_room"] = True
            d, _, _, _ = ZA.lees_week("vaste-id", "9100000001", KLOK)
            assert d["ruimte"]["toegangscode"] is None
            assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-06")["toestand"] == "goed"


def test_za4_trendfout_laat_opslag_en_za01_bekend():
    ant = gemeten_antwoorden()
    ant["/accounts/me/plans/usage"]["plan_recording"]["free_storage_usage"] = "10 GB"
    def lees(pad, params=None):
        if pad == "/report/cloud_recording":
            raise RuntimeError("proeffout")
        if pad == "/accounts/me/settings" and params:
            return {"sign_in_with_two_factor_auth": "none"} if params["option"] == "security" else \
                {"meeting_security": {"meeting_password": False}}
        return ant[pad]
    with patch.object(Z, "lees_account", side_effect=lees), patch.object(ZA.time, "sleep", return_value=None), \
         patch.object(Z, "PAUZE", 0):
        d, fouten, volledig, _ = ZA.lees_week("vaste-id", "9100000001", KLOK)
    assert volledig and any(naam == "opslagtrend" for _, naam, _ in fouten)
    assert d["opslag"]["pct"] == 100 and d["opslag"]["vol_rond"] is None
    assert d["opslagtrend"]["stand"].startswith("onbekend")
    week = ZA.weekoverzicht(d, ZA.adviezen(d), [], ZA.week_van(KLOK), KLOK, volledig)["inhoud"]
    assert week["delen"]["opnames"].startswith("onbekend") and week["opnames"]["opslag"]["pct"] == 100
    advies = next(a for a in ZA.adviezen(d) if a["code"] == "ZA-01")
    assert advies["toestand"] == "open" and "None" not in advies["reden"]
    assert "vol rond" not in advies["reden"]
    d["account"]["recording.auto_delete_cmr"] = True
    assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-01")["toestand"] == "onbekend"
    d["account"]["recording.auto_delete_cmr"] = False
    noden = []
    ZA._noden(type("R", (), {"nood": lambda self, tekst, wie: noden.append(tekst)})(),
              fouten, volledig, d["opslag"])
    assert any("Zoom-cloudopslag vol" in n for n in noden)
    d["opslag"] = ZA.opslag({"plan_recording": {"free_storage": "10 GB", "plan_storage": "0",
                                                "free_storage_usage": "2 GB"}})
    assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-01")["toestand"] == "onbekend"
    d["opslagtrend"] = {"stand": "ok"}
    assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-01")["toestand"] == "goed"


def test_za4_scan_aan_volgt_normalisatie_van_werkwijze():
    spec = importlib.util.spec_from_file_location("werkwijze_naar_bord_proef",
                                                   os.path.join(os.path.dirname(HIER), "werkwijze_naar_bord.py"))
    W = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(W)
    basis = "## Accountscan  \r\nACCOUNTSCAN: aan  \r\n\r\n## Einde\r\n"
    assert ZA.scan_aan(basis) == ZA.scan_aan(W.genormaliseerd(basis)) is True
    assert not ZA.scan_aan(basis.replace("ACCOUNTSCAN: aan", "ACCOUNTSCAN: uit"))


def test_za4_klikpaden_zijn_zelfstandig_en_voorzichtig():
    p = ZA.KLIKPADEN
    assert "(te bevestigen)" in p["ZA-03"].splitlines()[0]
    assert "(te bevestigen)" not in p["ZA-03"].splitlines()[1]
    assert "ZA-03" not in p["ZA-14"]
    assert "Create audio transcript" in p["ZA-14"] and "lock icon > Lock > Save" in p["ZA-14"]
    assert "eigen app" in p["ZA-10"] and "niet verwijderen of uitzetten" in p["ZA-10"]
    d = proefstand()
    d3 = proefstand()
    d3["user"]["recording.recording_audio_transcript"] = False
    d14 = proefstand()
    d14["opnames"]["transcript_pct"] = 40
    for code in ("ZA-03", "ZA-10", "ZA-14"):
        stand = d3 if code == "ZA-03" else d14 if code == "ZA-14" else d
        advies = next(a for a in ZA.adviezen(stand) if a["code"] == code)
        assert advies["toestand"] == "open"
        voorstel = ZA.voorstel_van(advies, ZA.week_van(KLOK))
        assert "ZA-" not in voorstel["reden"]
        assert voorstel["reden"].endswith("Weigeren: ik vraag het bij dezelfde stand niet opnieuw.")
        if code == "ZA-14":
            assert "Create audio transcript > lock icon > Lock > Save" in voorstel["reden"]
    a8 = next(a for a in ZA.adviezen(d) if a["code"] == "ZA-08")
    tekst = ZA.voorstel_van(a8, ZA.week_van(KLOK))["reden"]
    assert "Please switch our account's Zoom AI deployment to Zoom-Hosted Models Only (ZMO)." in tekst
    assert "Nederlandse samenvattingen" in tekst


def test_za4_scannoden_blijven_drie_rondes_tot_nieuwe_volledige_scan():
    vol = proefstand()
    vol["opslag"]["pct"] = 100
    leeg = proefstand()
    leeg["opslag"]["pct"] = 20
    metingen = iter(((vol, [], True, 25), (leeg, [], True, 25)))
    class Agent:
        def __init__(self, naam):
            pass
        def klaarzet(self, items):
            return {"nieuw": len(items)}
        def log(self, *_):
            pass
    class R:
        werkwijze = "## Accountscan\nACCOUNTSCAN: aan\n"
        agent = Agent("zoom-wacht")
        def __init__(self):
            self.noden = []
        def nood(self, tekst, wie="mehdi"):
            self.noden.append(tekst)
        def bron(self, *_):
            pass
    staat = {"account": {"pakket": {"periode": "monthly", "hosts": 1}}}
    w = {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}}
    with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
         patch.object(Z, "leesapp_verboden", return_value=[]), \
         patch.object(ZA, "lees_week", side_effect=lambda *a: next(metingen)), \
         patch.object(ZA, "lees_wijziging", return_value=(proefstand(), [], 5)), \
         patch.object(ZA, "voorstellen_lezen", return_value=[]), \
         patch.object(ZA, "adviezen", return_value=[]), patch.object(ZA.bord, "Agent", Agent):
        rondes = []
        for klok in (KLOK, KLOK + timedelta(hours=1), KLOK + timedelta(hours=2), KLOK + timedelta(days=7)):
            r = R()
            ZA.ronde(r, w, staat, klok)
            rondes.append(r.noden)
    for noden in rondes[:3]:
        assert any("Zoom-cloudopslag vol" in n for n in noden), noden
        assert any("Zoom-pakket veranderd" in n for n in noden), noden
    assert not any("Zoom-cloudopslag vol" in n or "Zoom-pakket veranderd" in n for n in rondes[3])


def test_za6_geweigerd_za01_krijgt_geen_nieuwe_cyclus_na_trendfout():
    d = proefstand()
    d["opslag"] = {"stand": "ok", "pct": 70, "vol_dagen": 20, "vol_rond": "2026-11-15"}
    d["opslagtrend"] = {"stand": "ok"}
    staat = {}
    eerste = next(a for a in ZA.adviezen(d, staat_acc=staat) if a["code"] == "ZA-01")
    assert eerste["toestand"] == "open" and eerste["cyclus"] == 0
    geweigerd = {"parameters": json.dumps(ZA.voorstel_van(eerste, ZA.week_van(KLOK))["parameters"]),
                "status": "geweigerd", "ts": KLOK.isoformat()}
    d["opslag"] = {"stand": "ok", "pct": 72, "vol_dagen": None, "vol_rond": None}
    d["opslagtrend"] = {"stand": "onbekend: HTTP 500"}
    fout_week = next(a for a in ZA.adviezen(d, staat_acc=staat) if a["code"] == "ZA-01")
    gekozen, _ = ZA.te_versturen([fout_week], [geweigerd], KLOK + timedelta(days=7))
    assert fout_week["toestand"] == "onbekend" and not gekozen
    assert staat["regels"]["ZA-01"] == {"toestand": "open", "cyclus": 0}
    d["opslag"]["vol_dagen"] = 20
    d["opslag"]["vol_rond"] = "2026-11-22"
    d["opslagtrend"] = {"stand": "ok"}
    hersteld = next(a for a in ZA.adviezen(d, staat_acc=staat) if a["code"] == "ZA-01")
    gekozen, _ = ZA.te_versturen([hersteld], [geweigerd], KLOK + timedelta(days=7))
    assert hersteld["toestand"] == "open" and hersteld["cyclus"] == 0 and not gekozen


def test_za6_wijzigingsmeldingfout_bewaart_en_herhaalt_scannoden():
    vorig = proefstand()
    gewijzigd = proefstand()
    gewijzigd["account"]["in_meeting.waiting_room"] = False
    class Agent:
        def __init__(self, naam):
            pass
        def klaarzet(self, items):
            raise self.fout
        def log(self, *_):
            pass
    class R:
        werkwijze = "## Accountscan\nACCOUNTSCAN: aan\n"
        agent = Agent("zoom-wacht")
        def __init__(self):
            self.noden = []
        def nood(self, tekst, wie="mehdi"):
            self.noden.append(tekst)
        def bron(self, *_):
            pass
    for fout in (ZA.bord.BordOnbekend("proef"), TimeoutError("proef")):
        Agent.fout = fout
        staat = {"account": {"laatste_volledig": ZA.week_van(KLOK), "basis": ZA.basis_van(vorig),
                             "scannoden": {"opslag_vol": True, "pakket_veranderd": True,
                                           "rechten": ["report:read:operation_logs:admin"]}}}
        oude_basis = staat["account"]["basis"]
        r = R()
        with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
             patch.object(Z, "leesapp_verboden", return_value=[]), \
             patch.object(ZA, "lees_wijziging", return_value=(gewijzigd, [], 6)), \
             patch.object(ZA.bord, "Agent", Agent):
            ZA.ronde(r, {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}}, staat, KLOK)
            assert staat["account"]["wijziging_fouten"] == 1
            r2 = R()
            ZA.ronde(r2, {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}},
                     staat, KLOK + timedelta(hours=1))
        assert ZA.NOOD_OPSLAG_VOL in r.noden and ZA.NOOD_PAKKET in r.noden
        assert ZA.NOOD_OPSLAG_VOL in r2.noden and ZA.NOOD_PAKKET in r2.noden
        assert any("report:read:operation_logs:admin" in nood for nood in r.noden)
        assert not any("nog niet gelukt" in nood for nood in r.noden + r2.noden)
        assert "Zoom-wijzigingscontrole twee rondes na elkaar niet gelezen" in r2.noden
        assert staat["account"]["basis"] == oude_basis
        assert staat["account"]["scannoden"]["opslag_vol"] is True
        assert staat["account"]["wijziging_fouten"] == 2


def test_za6_opslag_vol_sluit_bij_gedeeltelijke_scan_met_nieuwe_meting():
    d = proefstand()
    d["opslag"]["pct"] = 40
    class Agent:
        def __init__(self, naam):
            pass
        def klaarzet(self, items):
            return {"nieuw": len(items)}
        def log(self, *_):
            pass
    class R:
        werkwijze = "## Accountscan\nACCOUNTSCAN: aan\n"
        agent = Agent("zoom-wacht")
        def __init__(self):
            self.noden = []
        def nood(self, tekst, wie="mehdi"):
            self.noden.append(tekst)
        def bron(self, *_):
            pass
    staat = {"account": {"scannoden": {"opslag_vol": True}}}
    r = R()
    with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
         patch.object(Z, "leesapp_verboden", return_value=[]), \
         patch.object(ZA, "lees_week", return_value=(d, [("beveiliging", "logboek", "HTTP 500")], False, 25)), \
         patch.object(ZA, "voorstellen_lezen", return_value=[]), \
         patch.object(ZA, "te_versturen", return_value=([], [])), patch.object(ZA.bord, "Agent", Agent):
        ZA.ronde(r, {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}}, staat, KLOK)
    assert any("nog niet gelukt" in nood for nood in r.noden)
    assert ZA.NOOD_OPSLAG_VOL not in r.noden
    assert staat["account"]["scannoden"]["opslag_vol"] is False


def test_za8_rechtenalarm_sluit_pas_na_geslaagde_herlezing_van_de_bron():
    ant = gemeten_antwoorden()
    recht = "report:read:cloud_recording:admin"
    trendstand = ["geen recht", "HTTP 500", "ok"]
    weekresultaten = []
    echte_lees_week = ZA.lees_week

    def lees(pad, params=None):
        if pad == "/report/cloud_recording":
            if trendstand[0] == "geen recht":
                raise Z.GeenRecht(recht)
            if trendstand[0] == "HTTP 500":
                raise Z.AccountFout(http=500)
        if pad == "/accounts/me/settings" and params:
            return {"sign_in_with_two_factor_auth": "none"} if params["option"] == "security" else \
                {"meeting_security": {"meeting_password": False}}
        return ant[pad]

    def lees_week(*args):
        uit = echte_lees_week(*args)
        weekresultaten.append(uit)
        return uit

    class Agent:
        def __init__(self, naam):
            pass
        def klaarzet(self, items):
            return {"nieuw": len(items)}
        def log(self, *_):
            pass

    class R:
        werkwijze = "## Accountscan\nACCOUNTSCAN: aan\n"
        agent = Agent("zoom-wacht")
        def __init__(self):
            self.noden = []
        def nood(self, tekst, wie="mehdi"):
            self.noden.append(tekst)
        def bron(self, *_):
            pass

    staat = {}
    w = {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}}
    noden, bewaarde_rechten = [], []
    with patch.object(Z, "lees_account", side_effect=lees), patch.object(ZA.time, "sleep", return_value=None), \
         patch.object(Z, "PAUZE", 0), patch.object(Z, "leesapp", return_value=True), \
         patch.object(Z, "leesapp_fout", return_value=""), patch.object(Z, "leesapp_verboden", return_value=[]), \
         patch.object(ZA, "lees_week", side_effect=lees_week), patch.object(ZA, "adviezen", return_value=[]), \
         patch.object(ZA, "voorstellen_lezen", return_value=[]), patch.object(ZA.bord, "Agent", Agent):
        for week, stand in enumerate(("geen recht", "HTTP 500", "ok")):
            trendstand[0] = stand
            r = R()
            ZA.ronde(r, w, staat, KLOK + timedelta(days=7 * week))
            noden.append(r.noden)
            bewaarde_rechten.append(list(staat["account"]["scannoden"]["rechten"]))

    melding = f"Zoom-leesapp mist het recht {recht} voor de accountscan"
    assert all(uit[2] for uit in weekresultaten), weekresultaten
    assert any(f[1:] == ("opslagtrend", "geen recht " + recht) for f in weekresultaten[0][1])
    assert any(f[1:] == ("opslagtrend", "HTTP 500") for f in weekresultaten[1][1])
    assert melding in noden[0] and melding in noden[1], noden
    assert melding not in noden[2], noden
    assert bewaarde_rechten == [[{"bron": "opslagtrend", "recht": recht}],
                               [{"bron": "opslagtrend", "recht": recht}], []], bewaarde_rechten


def _za9_proefweek(*, fout_type=None, detail=None, pagineer=False, wijziging=False):
    """Uitsluitend verzonnen API-antwoorden met de gemeten Marketplace-vorm."""
    ant = gemeten_antwoorden()
    ant["/marketplace/apps/abcdef"] = detail if detail is not None else {
        "app_scopes": [{"scope_name": "meeting:read:meeting:admin"}]}
    ant["/marketplace/apps/ghijkl"] = {"app_scopes": [{"scope_name": "user:read:user:admin"}]}
    gevraagd = []

    def lees(pad, params=None):
        if pad == "/accounts/me/settings" and params:
            return {"sign_in_with_two_factor_auth": "none"} if params["option"] == "security" else \
                {"meeting_security": {"meeting_password": False}}
        if pad == "/marketplace/apps":
            gevraagd.append(dict(params))
            soort = params["type"]
            if soort == fout_type:
                raise Z.AccountFout(404)
            if soort != "account_added":
                return {"apps": []}
            if pagineer and params.get("next_page_token"):
                return {"apps": [{"app_id": "ghijkl", "app_name": "Verzonnen Lezer",
                                  "app_status": "PUBLISHED"}]}
            eerste = {"apps": list(ant["/marketplace/apps"]["apps"])}
            if pagineer:
                eerste["apps"] += [{"app_id": f"fictief{i:03d}", "app_name": "Verzonnen App",
                                    "app_status": "PUBLISHED"} for i in range(99)]
                eerste["next_page_token"] = "volgende"
            return eerste
        if pad.startswith("/marketplace/apps/") and pad not in ant:
            return {"app_scopes": [{"scope_name": "meeting:read:meeting:admin"}]}
        return ant[pad]

    with patch.object(Z, "lees_account", side_effect=lees), patch.object(ZA.time, "sleep", return_value=None), \
         patch.object(Z, "PAUZE", 0):
        d, fouten, volledig, vragen = ZA.lees_week("vaste-id", "9100000001", KLOK)
        wijzig = ZA.lees_wijziging("vaste-id", KLOK, ZA.basis_van(d)) if wijziging else None
    return d, fouten, volledig, vragen, gevraagd, wijzig


def test_bouw_za9_app_scopes_gaan_voor_beschrijvende_scopes():
    detail = {"app_scopes": [{"scope_name": "meeting:read:meeting:admin"},
                             {"scope_name": "meeting:write:meeting:admin"}],
              "scopes": ["View and manage your meetings"]}
    assert ZA._rechten_detail(detail) == (2, 1)


def test_bouw_za9_zonder_app_scopes_blijft_app_leesbaar_met_onbekende_rechten():
    rows = [{"app_id": "fictiefa", "app_name": "Verzonnen Planner", "app_status": "PUBLISHED"}]
    a = ZA.apps(rows, {"fictiefa": {"scopes": ["View and manage your meetings"]}})
    assert a["stand"] == "ok" and a["aantal"] == 1 and a["onbekende_rechten"] == 1
    assert a["overzicht"][0]["rechten"] is None and a["overzicht"][0]["schrijf"] is None
    assert a["met_schrijfrechten"] == []


def test_bouw_za9_ongeldige_scope_name_telt_niet_als_nul_of_als_fallback():
    rows = [{"app_id": "fictiefb", "app_name": "Verzonnen Notities", "app_status": "PUBLISHED"}]
    detail = {"app_scopes": [{"scope_name": "meeting:read:meeting:admin"},
                             {"scope_name": "View and manage your meetings", "scope": "meeting:write"}]}
    a = ZA.apps(rows, {"fictiefb": detail})
    assert a["stand"] == "ok" and a["onbekende_rechten"] == 1
    assert a["overzicht"][0]["rechten"] is None and a["overzicht"][0]["schrijf"] is None


def test_bouw_za9_za10_en_weekoverzicht_onderscheiden_onbekend_open_goed():
    d = proefstand()
    onbekend = {"code": "aaaaaaaaaaaaaaaa", "naam": "externe app", "gepubliceerd": True,
                "rechten": None, "schrijf": None}
    d["apps"] = {"stand": "ok", "aantal": 1, "eigen": 0, "overzicht": [onbekend],
                 "met_schrijfrechten": [], "onbekende_rechten": 1}
    advies = lambda: next(a for a in ZA.adviezen(d) if a["code"] == "ZA-10")
    assert advies()["toestand"] == "onbekend"
    w = ZA.weekoverzicht(d, [], [], ZA.week_van(KLOK), KLOK, True)["inhoud"]
    assert w["apps"]["aantal"] == 1 and w["apps"]["onbekende_rechten"] == 1
    zwaar = {"code": "bbbbbbbbbbbbbbbb", "naam": "externe app", "gepubliceerd": True,
             "rechten": 6, "schrijf": 5}
    d["apps"]["overzicht"].append(zwaar)
    d["apps"]["met_schrijfrechten"] = [zwaar]
    d["apps"]["aantal"] = 2
    assert advies()["toestand"] == "open"
    assert "Minstens 1 app" in advies()["reden"] and "bij 1 app zijn de rechten onbekend" in advies()["reden"]
    d["apps"]["overzicht"] = [{**onbekend, "rechten": 1, "schrijf": 0}]
    d["apps"]["met_schrijfrechten"] = []
    d["apps"]["aantal"] = 1
    d["apps"]["onbekende_rechten"] = 0
    assert advies()["toestand"] == "goed"


def test_bouw_za9_onbekende_rechten_zijn_geen_gemeten_rechtenwijziging():
    code = "aaaaaaaaaaaaaaaa"
    vorige = {"apps": {code: {"naam": "externe app", "gepubliceerd": True,
                              "rechten": 4, "schrijf": 1}}}
    nu = {"overzicht": [{"code": code, "naam": "externe app", "gepubliceerd": True,
                         "rechten": None, "schrijf": None}]}
    assert ZA.apprechten_veranderd(vorige, nu)["overzicht"] == []


def test_bouw_za9_laatst_bekende_rechten_blijven_vergelijkbaar_na_onbekende_week():
    rows = [{"app_id": "fictiefc", "app_name": "Verzonnen Kalender", "app_status": "PUBLISHED"}]
    d = proefstand()
    d["apps"] = ZA.apps(rows, {"fictiefc": {"app_scopes": [
        {"scope_name": "meeting:read"}, {"scope_name": "meeting:write"}]}})
    eerste = ZA.basis_van(d)
    d["apps"] = ZA.apps(rows, {"fictiefc": {"scopes": ["View and manage your meetings"]}})
    assert ZA.apprechten_veranderd(eerste, d["apps"])["overzicht"] == []
    tussen = ZA.basis_van(d, eerste)
    code = d["apps"]["overzicht"][0]["code"]
    assert tussen["apps"][code]["rechten"] == 2 and tussen["apps"][code]["schrijf"] == 1
    d["apps"] = ZA.apps(rows, {"fictiefc": {"app_scopes": [
        {"scope_name": "meeting:read"}, {"scope_name": "meeting:write"},
        {"scope_name": "user:write"}]}})
    gewijzigd = ZA.apprechten_veranderd(tussen, d["apps"])["overzicht"]
    assert gewijzigd == [{"naam": "externe app", "rechten_van": 2, "rechten_naar": 3,
                          "schrijf_van": 1, "schrijf_naar": 2}]


def test_bouw_za11_onbekende_vergelijkingen_blijven_zichtbaar_naast_gemeten_wijzigingen():
    d = proefstand()
    code_bekend = "aaaaaaaaaaaaaaaa"
    code_onbekend = "bbbbbbbbbbbbbbbb"
    d["apps"]["overzicht"] = [
        {"code": code_bekend, "naam": "externe app", "gepubliceerd": True,
         "rechten": 3, "schrijf": 1},
        {"code": code_onbekend, "naam": "externe app", "gepubliceerd": True,
         "rechten": None, "schrijf": None},
    ]
    vorige = {"apps": {
        code_bekend: {"naam": "externe app", "gepubliceerd": True, "rechten": 2, "schrijf": 1},
        code_onbekend: {"naam": "externe app", "gepubliceerd": True, "rechten": 4, "schrijf": 0},
    }}
    d["app_rechten"] = ZA.apprechten_veranderd(vorige, d["apps"])
    assert d["app_rechten"]["stand"].startswith("onbekend")
    assert d["app_rechten"]["onbekende_vergelijkingen"] == 1
    assert d["app_rechten"]["overzicht"] == [
        {"naam": "externe app", "rechten_van": 2, "rechten_naar": 3,
         "schrijf_van": 1, "schrijf_naar": 1}]
    w = ZA.weekoverzicht(d, [], [], ZA.week_van(KLOK), KLOK, True)["inhoud"]["apps"]
    assert w["rechten_veranderd"] == d["app_rechten"]["overzicht"]
    assert w["onbekende_vergelijkingen"] == 1
    d["apps"]["overzicht"][0]["rechten"] = 2
    d["app_rechten"] = ZA.apprechten_veranderd(vorige, d["apps"])
    w = ZA.weekoverzicht(d, [], [], ZA.week_van(KLOK), KLOK, True)["inhoud"]["apps"]
    assert w["onbekende_vergelijkingen"] == 1
    assert isinstance(w["rechten_veranderd"], str) and w["rechten_veranderd"].startswith("onbekend")
    assert ZA.apprechten_veranderd(None, d["apps"])["onbekende_vergelijkingen"] == 2
    assert ZA.apprechten_veranderd(vorige, None)["onbekende_vergelijkingen"] is None
    assert ZA.apprechten_veranderd({"apps": {}}, d["apps"])["onbekende_vergelijkingen"] == 2
    assert ZA.apprechten_veranderd(vorige, {"overzicht": []})["onbekende_vergelijkingen"] == 2
    d["apps"]["overzicht"][1].update(rechten=4, schrijf=0)
    d["app_rechten"] = ZA.apprechten_veranderd(vorige, d["apps"])
    assert d["app_rechten"] == {"stand": "ok", "overzicht": [], "onbekende_vergelijkingen": 0}
    w = ZA.weekoverzicht(d, [], [], ZA.week_van(KLOK), KLOK, True)["inhoud"]["apps"]
    assert w["rechten_veranderd"] == [] and w["onbekende_vergelijkingen"] == 0
    d["apps"]["overzicht"][0]["rechten"] = 3
    bewijs = {code_bekend: {"rechten": 2, "schrijf": 1, "gemeten_week": ZA.week_van(KLOK)}}
    fallback = ZA.apprechten_veranderd({"apps": {}}, d["apps"], bewijs)
    assert fallback["onbekende_vergelijkingen"] == 1
    assert fallback["overzicht"] == [{"naam": "externe app", "rechten_van": 2, "rechten_naar": 3,
                                     "schrijf_van": 1, "schrijf_naar": 1}]


def test_bouw_za11_korte_scan_houdt_actuele_rechten_onbekend_en_bewaart_meetweek():
    d, fouten, volledig, _, _, wijzig = _za9_proefweek(wijziging=True)
    assert volledig and not [f for f in fouten if f[1] == "apps"]
    actuele_apps = wijzig[0]["apps"]
    assert actuele_apps["aantal"] == 1 and actuele_apps["onbekende_rechten"] == 1
    assert actuele_apps["overzicht"][0]["rechten"] is None
    assert actuele_apps["overzicht"][0]["schrijf"] is None
    assert next(a for a in ZA.adviezen({"apps": actuele_apps}) if a["code"] == "ZA-10")["toestand"] == "onbekend"
    eerste_week = ZA.week_van(KLOK)
    eerste = ZA.basis_van(d, week=eerste_week)
    volgende_week = ZA.week_van(KLOK + timedelta(days=7))
    tussen = ZA.basis_van(wijzig[0], eerste, week=volgende_week)
    code = actuele_apps["overzicht"][0]["code"]
    assert tussen["apps"][code]["rechten"] == 1
    assert tussen["apps"][code]["schrijf"] == 0
    assert tussen["apps"][code]["gemeten_week"] == eerste_week
    actueel = ZA.actuele_appmeting(wijzig[0], volgende_week)
    assert actueel["week"] == volgende_week and actueel["onbekende_rechten"] == 1
    assert actueel["apps"][code] == {"rechten": None, "schrijf": None}
    bewijs = ZA.laatst_bewezen_apprechten(
        {code: {"rechten": 1, "schrijf": 0, "gemeten_week": eerste_week}}, actueel)
    assert bewijs[code] == {"rechten": 1, "schrijf": 0, "gemeten_week": eerste_week}


def test_bouw_za11_mislukte_weekronde_schuift_rechtenbasis_niet_door():
    vorig = proefstand()
    huidig = proefstand()
    huidig["apps"]["overzicht"][0]["rechten"] = 11
    oude_week = ZA.week_van(KLOK - timedelta(days=7))
    class Agent:
        def __init__(self, naam):
            pass
        def log(self, *_):
            pass
    class R:
        werkwijze = "## Accountscan\nACCOUNTSCAN: aan\n"
        agent = Agent("zoom-wacht")
        def nood(self, *_):
            pass
        def bron(self, *_):
            pass
    for foute_stap in ("weekoverzicht", "gebruik"):
        staat = {"account": {"basis": ZA.basis_van(vorig, week=oude_week)}}
        vorige_basis = json.loads(json.dumps(staat["account"]["basis"]))
        geplaatst = []
        def schrijf(_agent, item):
            soort = item["inhoud"].get("soort", item["soort"])
            if soort == "weekoverzicht":
                geplaatst.append(item)
            return not (len(geplaatst) == 1 and soort == foute_stap)
        with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
             patch.object(Z, "leesapp_verboden", return_value=[]), \
             patch.object(ZA, "lees_week", return_value=(huidig, [], True, 24)), \
             patch.object(ZA, "adviezen", return_value=[]), \
             patch.object(ZA, "voorstellen_lezen", return_value=[]), \
             patch.object(ZA, "_schrijf_item", side_effect=schrijf), \
             patch.object(ZA.bord, "Agent", Agent):
            w = {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}}
            ZA.ronde(R(), w, staat, KLOK)
            assert staat["account"]["basis"] == vorige_basis, foute_stap
            code = huidig["apps"]["overzicht"][0]["code"]
            assert staat["account"]["laatst_bewezen_apprechten"][code] == {
                "rechten": 11, "schrijf": 6, "gemeten_week": ZA.week_van(KLOK)}
            ZA.ronde(R(), w, staat, KLOK)
            ZA.ronde(R(), w, staat, KLOK, forceer=True)
        assert len(geplaatst) == 3
        assert len({x["uniek"] for x in geplaatst}) == 1
        assert all(x["inhoud"]["apps"]["rechten_veranderd"][0]["rechten_van"] == 10
                   for x in geplaatst)
        assert staat["account"]["rechten_weekbasis"]["apps"][code]["rechten"] == 10
        assert staat["account"]["basis"]["apps"][code]["rechten"] == 11
        assert staat["account"]["basis"]["apps"][code]["gemeten_week"] == ZA.week_van(KLOK)


def test_bouw_za11_eerste_scan_wordt_weekbasis_voor_hermeting():
    huidig = proefstand()
    staat, overzichten = {}, []
    class Agent:
        def __init__(self, naam):
            pass
        def log(self, *_):
            pass
    class R:
        werkwijze = "## Accountscan\nACCOUNTSCAN: aan\n"
        agent = Agent("zoom-wacht")
        def nood(self, *_):
            pass
        def bron(self, *_):
            pass
    def schrijf(_agent, item):
        if item["inhoud"].get("soort") == "weekoverzicht":
            overzichten.append(item)
        return True
    with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
         patch.object(Z, "leesapp_verboden", return_value=[]), \
         patch.object(ZA, "lees_week", return_value=(huidig, [], True, 24)), \
         patch.object(ZA, "adviezen", return_value=[]), \
         patch.object(ZA, "voorstellen_lezen", return_value=[]), \
         patch.object(ZA, "_schrijf_item", side_effect=schrijf), \
         patch.object(ZA.bord, "Agent", Agent):
        w = {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}}
        ZA.ronde(R(), w, staat, KLOK)
        code = huidig["apps"]["overzicht"][0]["code"]
        assert staat["account"]["rechten_weekbasis"]["apps"][code]["rechten"] == 10
        huidig["apps"]["overzicht"][0]["rechten"] = 11
        ZA.ronde(R(), w, staat, KLOK, forceer=True)
    assert overzichten[0]["inhoud"]["apps"]["rechten_veranderd"].startswith("onbekend")
    assert overzichten[1]["inhoud"]["apps"]["rechten_veranderd"] == [
        {"naam": "externe app", "rechten_van": 10, "rechten_naar": 11,
         "schrijf_van": 6, "schrijf_naar": 6}]


def test_bouw_za14_onbekende_weekbasis_gebruikt_eerste_later_gemeten_rechten():
    rows = [{"app_id": "fictiefc", "app_name": "Verzonnen Kalender", "app_status": "PUBLISHED"}]
    standen = []
    for detail in ({"scopes": ["View and manage your meetings"]},
                   {"app_scopes": ["openid", "profile"]},
                   {"app_scopes": ["openid", "profile", "meeting:write:meeting:admin"]}):
        d = proefstand()
        d["apps"] = ZA.apps(rows, {"fictiefc": detail})
        standen.append((d, [], True, 24))
    assert [x[0]["apps"]["overzicht"][0]["rechten"] for x in standen] == [None, 2, 3]
    assert [x[0]["apps"]["overzicht"][0]["schrijf"] for x in standen] == [None, 0, 1]

    class Agent:
        def __init__(self, naam):
            pass
        def log(self, *_):
            pass
    class R:
        werkwijze = "## Accountscan\nACCOUNTSCAN: aan\n"
        agent = Agent("zoom-wacht")
        def nood(self, *_):
            pass
        def bron(self, *_):
            pass
    overzichten = []
    def schrijf(_agent, item):
        if item["inhoud"].get("soort") == "weekoverzicht":
            overzichten.append(item["inhoud"]["apps"])
        return True
    staat = {}
    with patch.object(Z, "leesapp", return_value=True), patch.object(Z, "leesapp_fout", return_value=""), \
         patch.object(Z, "leesapp_verboden", return_value=[]), \
         patch.object(ZA, "lees_week", side_effect=standen), \
         patch.object(ZA, "adviezen", return_value=[]), \
         patch.object(ZA, "voorstellen_lezen", return_value=[]), \
         patch.object(ZA, "_schrijf_item", side_effect=schrijf), \
         patch.object(ZA.bord, "Agent", Agent):
        w = {"identiteit_ok": True, "ik": {"id": "vaste-id", "pmi": "9100000001"}}
        for uur in range(3):
            ZA.ronde(R(), w, staat, KLOK + timedelta(hours=uur), forceer=True)

    code = next(iter(staat["account"]["rechten_weekbasis"]["apps"]))
    assert staat["account"]["rechten_weekbasis"]["apps"][code]["rechten"] is None
    assert staat["account"]["rechten_weekbasis"]["apps"][code]["schrijf"] is None
    assert len(overzichten) == 3
    assert [x["onbekende_vergelijkingen"] for x in overzichten] == [1, 1, 0]
    assert all(x["rechten_veranderd"].startswith("onbekend") for x in overzichten[:2])
    assert overzichten[2]["rechten_veranderd"] == [
        {"naam": "externe app", "rechten_van": 2, "rechten_naar": 3,
         "schrijf_van": 0, "schrijf_naar": 1}]


def test_bouw_za9_marketplace_pagineert_met_honderd_in_beide_scans():
    d, fouten, volledig, _, gevraagd, wijzig = _za9_proefweek(pagineer=True, wijziging=True)
    assert volledig and d["apps"]["aantal"] == 101, fouten
    assert wijzig[0]["apps"]["aantal"] == 101
    assert all(p["page_size"] == 100 for p in gevraagd), gevraagd
    toegevoegd = [p for p in gevraagd if p["type"] == "account_added"]
    assert [p.get("next_page_token") for p in toegevoegd] == [None, "volgende", None, "volgende"]


def test_bouw_za9_elke_hulplijst_mag_falen_zonder_onvolledige_week():
    namen = {"account_created": "gemaakt", "active_requests": "aanvragen",
             "restricted_apps": "geblokkeerd", "approved_apps": "goedgekeurd"}
    for soort, naam in namen.items():
        d, fouten, volledig, _, _, _ = _za9_proefweek(fout_type=soort)
        assert volledig and d["apps"]["stand"] == "ok", (soort, fouten)
        assert d[naam] == {"stand": "onbekend: niet beschikbaar"}, (soort, d[naam])
        w = ZA.weekoverzicht(d, ZA.adviezen(d), [], ZA.week_van(KLOK), KLOK, volledig)["inhoud"]
        assert w["delen"]["apps"] == "ok" and w["apps"]["aantal"] == 1
        assert w["apps"]["gemaakte_apps" if naam == "gemaakt" else naam].startswith("onbekend")


def test_bouw_za9_gemeten_week_met_beschrijvingen_en_gemaakt_404_is_volledig():
    detail = {"app_scopes": [{"scope_name": "meeting:read:meeting:admin"},
                             {"scope_name": "meeting:write:meeting:admin"}],
              "scopes": ["View and manage your meetings"]}
    d, fouten, volledig, vragen, gevraagd, _ = _za9_proefweek(fout_type="account_created", detail=detail)
    assert volledig and vragen >= 20, fouten
    assert {naam for _, naam, _ in fouten} == {"facturen", "gemaakt"}
    assert d["apps"]["stand"] == "ok" and d["apps"]["onbekende_rechten"] == 0
    assert d["apps"]["overzicht"][0]["rechten"] == 2 and d["apps"]["overzicht"][0]["schrijf"] == 1
    assert next(a for a in ZA.adviezen(d) if a["code"] == "ZA-10")["toestand"] == "goed"
    assert all(p["page_size"] == 100 for p in gevraagd)
    w = ZA.weekoverzicht(d, ZA.adviezen(d), [], ZA.week_van(KLOK), KLOK, volledig)["inhoud"]
    assert w["scan"] == "volledig" and w["delen"]["apps"] == "ok"
    assert w["apps"]["onbekende_rechten"] == 0 and w["apps"]["gemaakte_apps"] == "onbekend: niet beschikbaar"


if __name__ == "__main__":
    import traceback
    fout = goed = 0
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
    sys.exit(bool(fout))
