"""De Anthropic-sleutel van de agents komt uit één bron: ~/appportal/.env (T-0064, 31-10-2026).

De sleutel in ~/agents/.env gaf sinds 14-10-2026 een 401; wie die als eerste las, viel stil uit. Alleen deze naam komt
hieruit (overleg X4): de andere instellingen (KENNIS_DSN, OPENAI_API_KEY, ...) houden hun eigen bron. Een sleutel die
al in de omgeving staat (shell, test) wint. Staat hij niet in ~/appportal/.env, dan blijft hij leeg en vult een latere
~/agents/.env hem niet meer (setdefault): de fout is dan 'geen sleutel', nooit een stille 401 op een oude sleutel.
De waarde komt nooit in een log.
"""
import os
import sys

BRON = "~/appportal/.env"
NAAM = "ANTHROPIC_API_KEY"


def waarde(pad=BRON, naam=NAAM):
    """De waarde van `naam` in het .env-bestand, of "" als die er niet is."""
    try:
        with open(os.path.expanduser(pad), encoding="utf-8") as bestand:
            for regel in bestand:
                k, _, v = regel.strip().partition("=")
                if k.strip().removeprefix("export ").strip() == naam:
                    return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def zet_anthropic(pad=BRON):
    """Zet ANTHROPIC_API_KEY uit ~/appportal/.env in de omgeving. Aanroepen vóór elke andere .env."""
    if os.environ.get(NAAM):
        return True
    os.environ[NAAM] = waarde(pad)
    if not os.environ[NAAM]:
        print(f"FOUT: geen {NAAM} in {BRON}, de enige sleutelbron van de agents (T-0064)", file=sys.stderr)
    return bool(os.environ[NAAM])
