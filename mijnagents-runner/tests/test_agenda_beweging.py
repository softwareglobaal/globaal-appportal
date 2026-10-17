"""De Agendawacht vertrouwt alleen een vers persoonlijk bewegingssignaal."""
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "koppelingen"))
import beweging as B  # noqa: E402

NU = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)


class Antwoord(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def opener(data):
    return lambda *_a, **_k: Antwoord(json.dumps(data).encode())


def payload(persoon=None, auto=None, gemaakt=NU):
    return {"gemaakt": gemaakt.isoformat(), "persoon": persoon or {"toestand": "niet_aangesloten"},
            "auto": auto or {"toestand": "onbekend"}}


def test_auto_alleen_wordt_nooit_mehdi_onderweg():
    auto = {"rol": "auto", "toestand": "auto_beweegt", "geldig_tot": (NU + timedelta(minutes=1)).isoformat()}
    uit = B.lees(NU.timestamp(), opener(payload(auto=auto)))
    assert uit["persoon"]["toestand"] == "niet_aangesloten"
    assert B.kort(uit) == "auto beweegt; persoon niet vastgesteld"


def test_persoonlijk_bewijs_vervalt_en_de_api_wordt_niet_gecachet():
    persoon = {"rol": "persoon", "toestand": "onderweg", "meettijd": (NU - timedelta(seconds=30)).isoformat(),
               "geldig_tot": (NU + timedelta(seconds=90)).isoformat()}
    assert B.lees(NU.timestamp(), opener(payload(persoon=persoon)))["persoon"]["toestand"] == "onderweg"
    verlopen = dict(persoon, geldig_tot=(NU - timedelta(seconds=1)).isoformat())
    assert B.lees(NU.timestamp(), opener(payload(persoon=verlopen)))["persoon"]["toestand"] == "onbekend"
    oud = payload(persoon=persoon, gemaakt=NU - timedelta(minutes=1))
    assert B.lees(NU.timestamp(), opener(oud))["persoon"]["toestand"] == "onbekend"


def test_niet_bereikbare_tegel_is_onbekend():
    def fout(*_a, **_k):
        raise OSError("geen verbinding")
    assert B.lees(NU.timestamp(), fout)["persoon"]["toestand"] == "onbekend"


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("geslaagd", naam)
            except Exception as fout:  # noqa: BLE001
                fouten += 1
                print("MISLUKT", naam, type(fout).__name__, fout)
    sys.exit(1 if fouten else 0)
