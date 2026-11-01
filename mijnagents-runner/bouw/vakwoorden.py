"""Wat van een zoekvraag naar buiten mag: alleen vakwoorden, getallen en eenheden (Codex controle 5, stopregel: het
ontwerp herbekeken). Een naam, een straat of een ander woord buiten deze lijst valt weg voor het naar het model en de
zoekmachine gaat; het verslag zegt welke woorden wegvielen. Zo hoeft geen patroon een naam te herkennen.

Een samengesteld woord telt als het uit stammen van de lijst bestaat (vloerverwarming = vloer + verwarming), met een
tussen-s of -e en een gewone uitgang. Een nieuw vakwoord voeg je hier toe, met een test.
"""
import re

STAMMEN = set("""
afbraak afbreek sloop graaf grond uitgraving riolering riool afvoer regenwater put septisch beerput drainage fundering
funderen paal sokkel kelder beton wapening staal ijzer metaal constructie ruw bouw metsel gevel steen blok snelbouw cellen
isolatie isoleer isolerend pur eps xps pir wol glas rots spouw dak plat hellend pan leien lei epdm roofing bitumen zink
goot regen pijp buis koepel licht raam velux kapel schouw schoorsteen timmer schrijn ramen deur poort garage buiten binnen
aluminium alu pvc hout glazing beglazing dubbel driedubbel vlieg rolluik zon wering screen pergola terras overkapping
veranda carport trap leuning balustrade hek afsluiting omheining tuin aanleg bestrating klinker oprit verharding plavei
tegel vloer chape dek giet parket laminaat vinyl tapijt plint plafond plafonneer pleister bepleistering gyproc gips karton
wand scheiding voorzet schilder verf behang spuit reiniging renovatie herstel herstelling vernieuw vernieuwing plaats
plaatsing levering lever vervang vervanging afwerking afwerk verbouwing nieuw uitbreiding optopping aanbouw keuken bad
kamer sanitair toilet wc douche lavabo kraan loodgieter leiding water warm koud verwarming centrale cv ketel condensatie
warmte pomp radiator ventilatie ventileer systeem airco koeling klimaat elektriciteit elektrisch elektra elektricien
bekabeling kabel verlichting punt stop contact schakelaar zekering keuring laad zonnepaneel paneel batterij thuis domotica
alarm camera brand werend rook melder gas mazout tank stabiliteit studie ingenieur epb asbest inventaris verwijdering
verwijder sanering vocht bestrijding injectie dichting waterdicht kit voeg scheur barst lift las smid smeed steiger stelling
container afval werf keet ontmanteling nuts voorziening aansluiting meter bekleding crepi sier strip ceder plaat golf
sandwich hal loods magazijn zolder vliering inbouw kast maatwerk meubel interieur damp scherm folie membraan opmeting
goten uitbraak uitbreek inloop aanverwant opbouw herbouw dakrand dakbedekking afdekking afdichting
plan plannen meetstaat bestek offerte prijs onderhoud onderaanneming aannemer aanneming vakman werk werken sierlijst lijst
houtskelet skelet prefab modulair kozijn dorpel venster vensterbank tablet natuursteen arduin marmer graniet blauwe hardsteen
composiet keramiek beglaasd draagmuur muur muren balk balken latei kolom ligger welf welfsel holle predal hourdis kanaal
kanalen ventilatiekanaal rookkanaal afzuig afzuiging dampkap boiler zonneboiler regenput infiltratie bufferbekken pomp
put gracht beschoeiing drainering grind zand kalk cement mortel lijm egaliseer egalisatie schuur polier coating hars epoxy
""".split())

FUNCTIE = set("""
de het een en of met zonder van voor bij in op aan te tot uit naar over onder boven achter naast per inclusief exclusief incl
excl nieuw nieuwe oud oude bestaand bestaande volledig volledige gedeeltelijk gedeeltelijke klein kleine groot grote enkel
enkele extra ongeveer circa ca totaal ook alle verdieping gelijkvloers eerste tweede derde vierde kamer kamers slaap woon
living hal inkom berging was voorkant achterkant zijkant woning appartement huis rij gebouw studio bureel kantoor winkel
horeca voor achter zij links rechts noord zuid oost west dubbele enkele hoge lage hoog laag breed lang diep dik dikte
""".split())

EENHEDEN = {"m", "m2", "m²", "m3", "m³", "lm", "st", "stuk", "stuks", "kg", "ton", "mm", "cm", "kw", "kwp", "kwh", "l",
            "liter", "uur", "dag", "dagen", "week", "weken", "maand", "maanden", "x", "%", "a", "b", "c", "d"}
UITGANGEN = ("", "en", "s", "e", "n", "er", "ers", "ing", "ingen", "werk", "werken", "es", "heid")
GETAL = re.compile(r"^\d{1,4}(?:[.,]\d{1,2})?(?:m2|m²|m3|m³|m|cm|mm|kw|kwp)?$")


def _samengesteld(w, cache=None):
    """Bestaat het woord uit stammen van de lijst (met een tussen-s of -e en een gewone uitgang)?"""
    cache = {} if cache is None else cache
    if w in cache:
        return cache[w]
    goed = False
    for uitgang in UITGANGEN:
        if uitgang and not w.endswith(uitgang):
            continue
        kern = w[:len(w) - len(uitgang)] if uitgang else w
        if kern in STAMMEN or kern in FUNCTIE:
            goed = True
            break
        for i in range(3, len(kern) - 2):
            links, rechts = kern[:i], kern[i:]
            if links in STAMMEN or links in FUNCTIE:
                for tussen in ("", "s", "e", "en"):
                    if rechts.startswith(tussen) and len(rechts) - len(tussen) >= 3 and \
                            _samengesteld(rechts[len(tussen):], cache):
                        goed = True
                        break
            if goed:
                break
        if goed:
            break
    cache[w] = goed
    return goed


def toegelaten(woord):
    w = woord.lower().strip(".,;:()'\"")
    if not w:
        return True
    if w in EENHEDEN or GETAL.match(w):
        return True
    return w.isalpha() and len(w) >= 2 and _samengesteld(w)


def filter_tekst(tekst):
    """(tekst die naar buiten mag, [weggelaten woorden]). Streepjes en schuine strepen splitsen woorden (PIR-isolatie)."""
    houden, weg = [], []
    for stuk in re.split(r"\s+", str(tekst or "").strip()):
        delen = [d for d in re.split(r"[-/]", stuk) if d]
        if delen and all(toegelaten(d) for d in delen):
            houden.append(stuk.strip(",;"))
        elif stuk.strip(".,;:()"):
            weg.append(stuk.strip(".,;:()"))
    return " ".join(houden).strip(), weg
