"""Postbus: doorsturen, de enige vorm van uitgaande post die deze server kent.

Dit is bewust een aparte module. `imapbron` blijft daardoor wat het altijd was,
een leesmodule zonder SMTP, en alles wat de deur uit kan staat op deze ene
plek bij elkaar. Wie wil weten wat er namens een mailbox naar buiten kan, hoeft
alleen dit bestand te lezen.

Wat hier met opzet niet kan:

1. **Een bericht opstellen.** Er gaat alleen post uit die al in de mailbox
   stond. De tekst die de agent toevoegt is een begeleidende notitie, en die
   staat los van het origineel: dat gaat onaangeroerd als bijlage mee.
2. **Een zelfgekozen bestemming.** Het adres wordt getoetst aan de lijst van
   de mailbox (`config.vereis_doorsturen`). Wat daar niet in staat, gaat niet.
3. **Ongemerkt versturen.** Elke doorsturing legt een kopie in de map
   Verzonden van de mailbox zelf, zodat de eigenaar in zijn eigen webmail ziet
   wat er namens hem is vertrokken. Mislukt die kopie, dan zeggen we dat.

De begrenzing zit verder in een noodrem en een dagplafond. Zonder
POSTBUS_DOORSTUREN=ja gaat er niets uit, ook niet als het bestand het
toestaat: dat is de schakelaar om een lopende koppeling in een keer stil te
zetten zonder aan de mailboxen te komen.
"""
import email
import imaplib
import os
import smtplib
import threading
import time
from datetime import date
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

import config
import imapbron

# Noodrem: standaard uit. Zet POSTBUS_DOORSTUREN=ja om doorsturen toe te staan.
JA = {"ja", "yes", "waar", "true", "aan"}
ACTIEF = os.environ.get("POSTBUS_DOORSTUREN", "").strip().lower() in JA
DAGPLAFOND = int(os.environ.get("POSTBUS_DOORSTUREN_DAGPLAFOND", "100"))
TIMEOUT = 30

# Deze kop zetten we op wat wij versturen. Komt hij op een binnengekomen
# bericht voorbij, dan kijken we naar iets dat zelf al een doorsturing was en
# stoppen we: anders stuurt een verkeerd gerichte regel post eindeloos rond.
EIGEN_KOP = "X-Postbus-Doorgestuurd"

_slot = threading.Lock()
_teller = {"dag": None, "aantal": 0}


def _huidige_dag():
    vandaag = date.today().isoformat()
    if _teller["dag"] != vandaag:
        _teller.update(dag=vandaag, aantal=0)
    return _teller


def _mag_nog():
    """True zolang het dagplafond nog niet bereikt is. Telt niets."""
    with _slot:
        return _huidige_dag()["aantal"] < DAGPLAFOND


def _tel_succes():
    """Telt een geslaagde verzending mee en geeft het aantal van vandaag.

    Alleen successen tellen. Een mislukte poging (bijvoorbeeld omdat de
    mailserver even afknijpt) mag het plafond niet opeten, anders stopt een
    tijdelijke storing de rest van de dag.
    """
    with _slot:
        dag = _huidige_dag()
        dag["aantal"] += 1
        return dag["aantal"]


def _verzondenmap(M):
    """De map Verzonden: eerst op de \\Sent-eigenschap, dan op naam."""
    lijst = imapbron._lijst_mappen(M)
    for attrs, naam in lijst:
        if "\\sent" in attrs:
            return naam
    for _, naam in lijst:
        kaal = naam.lower().rsplit(".", 1)[-1]
        if kaal in ("sent", "verzonden", "sent items", "sent messages"):
            return naam
    return None


def _samenvatting(bron):
    """De kopregels van het origineel, voor in de begeleidende tekst."""
    regels = []
    for veld, naam in (("From", "Van"), ("Date", "Datum"),
                       ("To", "Aan"), ("Subject", "Onderwerp")):
        waarde = imapbron._kop(bron.get(veld))
        if waarde:
            regels.append(f"{naam}: {waarde}")
    return "\n".join(regels)


def doorsturen(mailbox, mapnaam, uid, naar, notitie=None):
    """Stuurt een bericht uit de mailbox door naar een toegestaan adres.

    Het origineel gaat als bijlage mee (message/rfc822) en blijft dus precies
    zoals het binnenkwam, met afzender, datum en eventuele bijlagen intact.
    Dat is voor een boekhouding het bruikbaarst, en het voorkomt dat wij een
    bericht namens iemand anders lijken te ondertekenen.

    De leesstatus van het origineel blijft ongemoeid: ophalen gaat met PEEK.
    """
    bestemming = config.vereis_doorsturen(mailbox, naar)

    if not ACTIEF:
        raise ValueError(
            "Doorsturen staat uit op deze server (POSTBUS_DOORSTUREN). De "
            "mailbox staat het toe, de server niet. Vraag de beheerder de "
            "schakelaar om te zetten.")
    if not mailbox.get("smtp_host"):
        raise ValueError(f"Voor {mailbox['adres']} staat geen smtp_host in "
                         "mailboxen.yaml, dus er kan niets verstuurd worden.")

    bron_map = config.map_toegestaan(mailbox, mapnaam)

    with imapbron._Sessie(mailbox) as M:
        imapbron._selecteer(M, bron_map)
        ok, gegevens = M.uid("FETCH", str(int(uid)), "(BODY.PEEK[])")
        ruw = next((el[1] for el in (gegevens or []) if isinstance(el, tuple)),
                   None)
        if ok != "OK" or not ruw:
            raise ValueError(f"Geen bericht met uid {uid} in {bron_map}")
        bron = email.message_from_bytes(ruw)

        if bron.get(EIGEN_KOP):
            raise ValueError(
                "Dit bericht is zelf al een doorsturing van deze server. Het "
                "opnieuw doorsturen zou een lus kunnen opleveren, dus dat doen "
                "we niet.")

        afzender = parseaddr(imapbron._kop(bron.get("From")))[1].lower()
        if afzender and afzender == bestemming:
            raise ValueError(
                f"Dit bericht komt van {bestemming} en daar weer naartoe "
                "sturen levert heen en weer geschuif op. Overgeslagen.")

        onderwerp = imapbron._kop(bron.get("Subject")) or "(geen onderwerp)"
        if not _mag_nog():
            raise ValueError(
                f"Dagplafond van {DAGPLAFOND} doorsturingen bereikt. Er gaat "
                "vandaag niets meer uit; morgen telt hij opnieuw.")

        bericht = EmailMessage()
        bericht["From"] = mailbox["adres"]
        bericht["To"] = bestemming
        bericht["Subject"] = (onderwerp if onderwerp.lower().startswith("fwd:")
                              else "Fwd: " + onderwerp)
        bericht["Date"] = formatdate(localtime=True)
        bericht["Message-ID"] = make_msgid()
        bericht[EIGEN_KOP] = f"{mailbox['adres']} {bron_map} uid {uid}"

        inleiding = str(notitie or "").strip()
        tekst = (f"{inleiding}\n\n" if inleiding else "")
        tekst += ("Doorgestuurd vanuit de mailbox " + mailbox["adres"] +
                  ".\nHet oorspronkelijke bericht zit onaangeroerd als "
                  "bijlage bij dit bericht.\n\n" + _samenvatting(bron))
        bericht.set_content(tekst)
        bericht.add_attachment(ruw, maintype="message", subtype="rfc822",
                               filename=(onderwerp[:60].strip() or "bericht")
                               + ".eml")

        try:
            with smtplib.SMTP_SSL(mailbox["smtp_host"], mailbox["smtp_poort"],
                                  timeout=TIMEOUT) as s:
                s.login(mailbox["gebruiker"], mailbox["wachtwoord"])
                s.send_message(bericht)
        except Exception as e:
            raise ValueError(f"Versturen naar {bestemming} mislukte "
                             f"({type(e).__name__}: {e}). Er is niets "
                             "vertrokken.")

        # Nu is het echt de deur uit; pas hier telt het mee voor het dagplafond.
        vandaag = _tel_succes()

        # SMTP levert alleen af; de map Verzonden vult je mailprogramma normaal
        # zelf. Zonder deze kopie zou een doorsturing door de server nergens in
        # de mailbox terug te zien zijn, en juist dat is hier het bewijsstuk.
        doelmap = _verzondenmap(M)
        bewaard = False
        if doelmap:
            try:
                ok, _ = M.append(f'"{doelmap}"', "(\\Seen)",
                                 imaplib.Time2Internaldate(time.time()),
                                 bericht.as_bytes())
                bewaard = ok == "OK"
            except Exception:
                bewaard = False

    print(f"[postbus] doorgestuurd {mailbox['adres']} {bron_map} uid {uid} "
          f"naar {bestemming}: {onderwerp[:80]}", flush=True)

    uit = {"mailbox": mailbox["adres"], "map": bron_map, "uid": int(uid),
           "naar": bestemming, "onderwerp": bericht["Subject"],
           "verstuurd": True, "kopie_in_verzonden": bewaard,
           "vandaag_verstuurd": vandaag, "dagplafond": DAGPLAFOND}
    if not bewaard:
        uit["let_op"] = ("Het bericht is verstuurd, maar de kopie in Verzonden "
                         "lukte niet. In de mailbox is de doorsturing dus niet "
                         "terug te zien.")
    return uit
