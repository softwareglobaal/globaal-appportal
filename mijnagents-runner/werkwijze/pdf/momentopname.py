import os, sys, json
sys.path.insert(0, os.path.expanduser("~/appportal/mijnagents-runner")); sys.path.insert(0, os.path.expanduser("~/appportal/mijnagents-runner/koppelingen"))
import agenda_wacht as W
zc = json.load(open(os.path.expanduser("~/appportal/mijnagents-data/zelfcontrole.json")))
print(json.dumps({"firmacodes": W.FIRMACODES, "soort": W.SOORT, "types": W.TYPES, "oude_codes": W.AGENDACODE_NAAR_FIRMA,
                  "externe_firmas": W.EXTERNE_FIRMAS, "relaties": [{"naam": r.get("naam"), "rol": r.get("rol") or r.get("wat"), "firma": r.get("firma")} for r in W.EXTERNE_RELATIES],
                  "kanteldatum": W.KANTELDATUM, "ronde_uren": W.RONDE_UREN, "plafond": W.ROUTES_PLAFOND, "buffer": W.BUFFER_MIN,
                  "zelfcontrole": zc}, ensure_ascii=False, default=str))
