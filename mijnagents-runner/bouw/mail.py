"""De prijsaanvraag van De Aannemerszoeker: een vast sjabloon per firma, door de code samengesteld.

Het taalmodel schrijft alleen de werkomschrijving (wat er moet gebeuren, uit de vraag). Afzender, aanhef, de vragen
aan de firma, de termijn en de handtekening komen uit dit bestand, zodat de context altijd die van de ene firma is.
Het werfadres en de projectnaam vult de code in; die gaan nooit naar het model.

H-Architects: zoals de mails van standaard@ en light@ (bv. 2145, 06-10-2026): de architect vraagt een offerte voor de
bouwheer, plannen in bijlage, plaatsbezoek op afspraak, ondertekend "In opdracht van H-Architects BV".
Harmonie Bouw: de aannemer vraagt een onderaannemer om een prijs, btw verlegd (medecontractant), met verzekering.

Elke mail gaat door scheiding.schendingen (rol mail). Haalt ze die niet, dan bestaat ze niet.
"""
from . import scheiding as S

FIRMA = {
    S.HA: {
        "naam": "H-Architects",
        "afzender": {"standaard": "standaard@h-architects.be", "light": "light@h-architects.be"},
        "onderwerp": "{project}Prijsaanvraag {werk}",
        "inleiding": "Voor een project van onze bouwheer in {gemeente} zoeken wij een firma voor {werk}.",
        "vragen": [
            "een prijs per post, exclusief btw, met het btw-tarief dat u toepast;",
            "wat inbegrepen is en wat niet;",
            "de geldigheid van de offerte en uw vroegste uitvoeringsdatum.",
        ],
        "slot": ("Gelieve de offerte op te maken op naam van de bouwheer; zijn gegevens bezorgen wij u bij uw "
                 "bevestiging. De plannen vindt u in bijlage{meetstaat}. Een plaatsbezoek kan op afspraak."),
        "groet": "Met vriendelijke groeten/Kind regards,",
        "handtekening": ["In opdracht van H-Architects BV,", "", "E-mail: {afzender}", "Telefoon: +32 16 79 32 96",
                         "Website: www.h-architects.be", "Werkuren: 10:00 u tot 17:00 u"],
    },
    S.HB: {
        "naam": "Harmonie Bouw",
        "afzender": {"standaard": "kantoor@harmoniebouw.be"},
        "onderwerp": "Prijsaanvraag onderaanneming: {werk} in {gemeente}",
        "inleiding": "Voor een werf in {gemeente} zoeken wij een onderaannemer voor {werk}.",
        "vragen": [
            "een prijs per post, exclusief btw (btw verlegd, medecontractant);",
            "wat inbegrepen is en wat niet (materiaal, afvoer, stellingen);",
            "uw beschikbaarheid en de uitvoeringstermijn;",
            "uw ondernemingsnummer en een attest van uw verzekering burgerlijke aansprakelijkheid.",
        ],
        "slot": "Plannen en details bezorgen wij u op vraag{meetstaat}. Een plaatsbezoek kan op afspraak.",
        "groet": "Met vriendelijke groeten,",
        "handtekening": ["Harmonie Bouw BV", "E-mail: {afzender}"],
    },
}


class MailGeweigerd(Exception):
    """Een prijsaanvraag die de scheidingsgrendel niet haalt: ze wordt nooit klaargezet."""

    def __init__(self, redenen):
        super().__init__("; ".join(redenen))
        self.redenen = redenen


def afzender(firma, reeks="standaard"):
    adressen = FIRMA[firma]["afzender"]
    return adressen.get(reeks) or adressen["standaard"]


def maak(firma, werk, werkomschrijving, gemeente, tegen=None, project="", reeks="standaard", met_meetstaat=False,
         aanhef="Beste,", extra_kenmerken=None):
    """{"van", "onderwerp", "tekst"} van een prijsaanvraag, of MailGeweigerd.
    werk: kort (bv. 'plafonneerwerken'); werkomschrijving: de alinea van het model; gemeente: van de werf;
    tegen: datum (dd-mm-jjjj) waartegen de prijs er graag is; project: bv. '2145 - Vertommensberg 9, 3010 Kessel-Lo'
    (alleen bij H-Architects, zoals in hun onderwerpregels)."""
    f = FIRMA[firma]
    van = afzender(firma, reeks)
    werk = " ".join(str(werk or "").split()).strip(" .;") or "de werken"
    gemeente = " ".join(str(gemeente or "").split()) or "uw regio"
    meetstaat = " samen met de meetstaat" if met_meetstaat else ""
    voor_project = f"{project} - " if project and firma == S.HA else ""
    onderwerp = f["onderwerp"].format(project=voor_project, werk=werk, gemeente=gemeente)
    delen = [aanhef, "", f["inleiding"].format(gemeente=gemeente, werk=werk)]
    omschrijving = " ".join(str(werkomschrijving or "").split())
    if omschrijving:
        delen += ["", omschrijving]
    delen += ["", "Graag ontvangen wij uw offerte met:" if firma == S.HA else "Graag ontvangen wij uw prijs met:"]
    delen += [f" * {v}" for v in f["vragen"]]
    delen += ["", f["slot"].format(meetstaat=meetstaat)]
    if tegen:
        delen += [f"Wij ontvangen uw {'offerte' if firma == S.HA else 'prijs'} graag tegen {tegen}."]
    delen += ["", "Alvast bedankt.", "", f["groet"]] + [r.format(afzender=van) for r in f["handtekening"]]
    tekst = "\n".join(delen)
    redenen = S.schendingen(onderwerp + "\n" + tekst + "\n" + van, firma, extra_kenmerken)
    if redenen:
        raise MailGeweigerd(redenen)
    return {"van": van, "onderwerp": onderwerp, "tekst": tekst}
