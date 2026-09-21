"""Opgemaakte meldingsmail voor een aanvraag die via een website binnenkwam.

Waarom deze module hier staat en niet in de website: de mail moet een knop
bevatten die rechtstreeks de Pipedrive-deal opent. Het dealnummer bestaat pas
nadat aanvraag_verwerk.py de deal heeft aangemaakt, dus moet de mail ook van
hieruit vertrekken. De sales-collega ziet zo één ongelezen bericht in de inbox
en klikt van daaruit door naar het dossier.

Afspraak over alle eigen sites: een ingevuld webformulier komt binnen als een
opgemaakte mail in de huisstijl, nooit als kale tekst.

E-mailclients (Outlook voorop) negeren <style>-blokken en moderne CSS. Daarom
tabellen voor de opbouw en alle stijl inline. Bewust geen afbeeldingen: die
worden standaard geblokkeerd en het logo zou een leeg kader worden.
"""
import html
import re
import smtplib
import ssl
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage

MERK = "#5450e0"
INKT = "#16162a"
TEKST = "#45455c"
ZACHT = "#6e6e88"
LIJN = "#e5e5ef"
VLAK = "#fafaff"

# Per firma de merknaam en het Pipedrive-bedrijfsdomein, zodat dezelfde module
# straks ook voor de andere sites bruikbaar is.
FIRMAS = {
    "unabo-site": {"naam": "UNABO", "pipedrive": "unabo"},
    "tkn-site": {"naam": "TKN-Buro", "pipedrive": "tkn-buro-tekenwerk"},
}


def dealadres(bron: str, deal_id) -> str:
    """Het webadres van de deal, of leeg als wij de firma niet kennen."""
    firma = FIRMAS.get(bron)
    if not firma or not deal_id:
        return ""
    return f"https://{firma['pipedrive']}.pipedrive.com/deal/{deal_id}"


def _v(waarde) -> str:
    """Tekst veilig in HTML zetten; aanvragen komen van buiten."""
    return html.escape("" if waarde is None else str(waarde), quote=True)


def _rij(naam: str, waarde, link: str = "") -> str:
    if not waarde:
        return ""
    inhoud = (
        f'<a href="{_v(link)}" style="color:{MERK};text-decoration:none;">{_v(waarde)}</a>'
        if link else _v(waarde)
    )
    return (
        f'<tr>'
        f'<td style="padding:9px 0;border-bottom:1px solid {LIJN};color:{ZACHT};'
        f'font-size:13px;width:170px;vertical-align:top;">{_v(naam)}</td>'
        f'<td style="padding:9px 0;border-bottom:1px solid {LIJN};color:{INKT};'
        f'font-size:14px;font-weight:600;">{inhoud}</td>'
        f'</tr>'
    )


def onderwerp(a: dict) -> str:
    diensten = a.get("diensten") or []
    dienst = diensten[0] if diensten else "Offerteaanvraag"
    wie = (a.get("adres") or "").strip() or f"{a.get('voornaam','')} {a.get('achternaam','')}".strip()
    return f"Offerteaanvraag {dienst}" + (f" · {wie}" if wie else "")


def als_tekst(a: dict, deal_url: str = "") -> str:
    regels = []
    if deal_url:
        regels += [f"Deal in Pipedrive: {deal_url}", ""]
    regels += [
        f"Diensten: {', '.join(a.get('diensten') or []) or 'niet opgegeven'}",
        f"Naam: {a.get('voornaam','')} {a.get('achternaam','')}".rstrip(),
        f"E-mail: {a.get('email','')}",
        f"Telefoon: {a.get('telefoon','')}",
        f"Adres project: {a.get('adres','')}",
        f"Type gebouw: {a.get('gebouwtype') or '-'}",
        f"Aard van de werken: {a.get('type_aanvraag') or '-'}",
        f"Gevonden via: {a.get('gevonden_via') or '-'}",
        f"Pagina: {a.get('pagina','')}",
        "", "Bericht:", a.get("omschrijving", ""),
    ]
    return "\n".join(regels)


def als_html(a: dict, deal_url: str = "") -> str:
    naam = f"{a.get('voornaam','')} {a.get('achternaam','')}".strip()
    diensten = a.get("diensten") or []
    labels = "".join(
        f'<span style="display:inline-block;background:#eeeeff;color:#3d38ad;'
        f'font-size:12px;font-weight:600;padding:5px 11px;border-radius:999px;'
        f'margin:0 6px 6px 0;">{_v(d)}</span>'
        for d in diensten
    ) or f'<span style="color:{ZACHT};font-size:13px;">Niet opgegeven</span>'

    try:
        stip = datetime.fromisoformat(str(a.get("tijdstip", "")).replace("Z", "+00:00"))
    except ValueError:
        stip = datetime.now(timezone.utc)
    # Brussel is UTC+2 in de zomer; de aanvraag draagt geen tijdzone mee.
    moment = (stip + timedelta(hours=2)).strftime("%d-%m-%Y om %H:%M")

    # De belangrijkste knop staat bovenaan: de collega moet niet scrollen om
    # bij het dossier te komen.
    knop_boven = ""
    if deal_url:
        knop_boven = (
            f'<tr><td style="padding:22px 28px 4px;">'
            f'<a href="{_v(deal_url)}" style="display:block;background:{MERK};color:#ffffff;'
            f'font-size:15px;font-weight:600;text-decoration:none;padding:14px 22px;'
            f'border-radius:10px;text-align:center;">Deze aanvraag behandelen in Pipedrive</a>'
            f'<div style="color:{ZACHT};font-size:12px;text-align:center;padding-top:8px;">'
            f'De deal is al aangemaakt en staat op u te wachten.</div>'
            f'</td></tr>'
        )

    tel = re.sub(r"[^\d+]", "", str(a.get("telefoon") or ""))
    email = a.get("email") or ""

    return f"""<!doctype html>
<html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_v(onderwerp(a))}</title></head>
<body style="margin:0;padding:0;background:{VLAK};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{VLAK};padding:28px 12px;">
<tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid {LIJN};border-radius:14px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">

    <tr><td style="background:{INKT};padding:22px 28px;">
      <div style="color:#ffffff;font-size:17px;font-weight:700;letter-spacing:.02em;">{_v(FIRMAS.get(a.get('bron', ''), {}).get('naam', 'Aanvraag'))}</div>
      <div style="color:#b9b9d4;font-size:12px;margin-top:3px;">Nieuwe offerteaanvraag via de website</div>
    </td></tr>

    {knop_boven}

    <tr><td style="padding:22px 28px 6px;">
      <div style="color:{ZACHT};font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:9px;">Gevraagde diensten</div>
      {labels}
    </td></tr>

    <tr><td style="padding:14px 28px 4px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        {_rij('Naam', naam)}
        {_rij('E-mail', email, f'mailto:{email}' if email else '')}
        {_rij('Telefoon', a.get('telefoon'), f'tel:{tel}' if tel else '')}
        {_rij('Adres project', a.get('adres'))}
        {_rij('Type gebouw', a.get('gebouwtype'))}
        {_rij('Aard van de werken', a.get('type_aanvraag'))}
        {_rij('Gevonden via', a.get('gevonden_via'))}
      </table>
    </td></tr>

    <tr><td style="padding:22px 28px 6px;">
      <div style="color:{ZACHT};font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">Bericht van de klant</div>
      <div style="background:{VLAK};border-left:3px solid {MERK};border-radius:0 8px 8px 0;padding:14px 16px;color:{TEKST};font-size:14px;line-height:1.65;white-space:pre-wrap;">{_v(a.get('omschrijving'))}</div>
    </td></tr>

    <tr><td style="padding:20px 28px 26px;">
      <a href="mailto:{_v(email)}" style="display:inline-block;background:#ffffff;color:{INKT};border:1px solid {LIJN};font-size:14px;font-weight:600;text-decoration:none;padding:11px 20px;border-radius:9px;">Rechtstreeks antwoorden</a>
    </td></tr>

    <tr><td style="background:{VLAK};border-top:1px solid {LIJN};padding:15px 28px;color:{ZACHT};font-size:12px;line-height:1.6;">
      Ingediend op {_v(moment)}<br>
      Via pagina <span style="color:{TEKST};">{_v(a.get('pagina'))}</span>
    </td></tr>

  </table>
</td></tr>
</table>
</body></html>"""


def verstuur(a: dict, deal_id=None, *, instellingen: dict, droog: bool = False):
    """Stuurt de meldingsmail. `instellingen` bevat de SMTP-gegevens.

    Faalt nooit hard: een aanvraag die wél in Pipedrive staat mag niet
    verloren gaan omdat de mailserver even niet meewerkt. De aanroeper logt.
    """
    url = dealadres(a.get("bron", ""), deal_id)
    bericht = EmailMessage()
    bericht["Subject"] = onderwerp(a)
    bericht["From"] = instellingen["van"]
    bericht["To"] = instellingen["naar"]
    if a.get("email"):
        bericht["Reply-To"] = a["email"]
    bericht.set_content(als_tekst(a, url))
    bericht.add_alternative(als_html(a, url), subtype="html")

    if droog:
        return bericht

    context = ssl.create_default_context()
    poort = int(instellingen.get("poort", 465))
    if instellingen.get("beveiligd", True):
        with smtplib.SMTP_SSL(instellingen["host"], poort, context=context, timeout=20) as s:
            s.login(instellingen["gebruiker"], instellingen["wachtwoord"])
            s.send_message(bericht)
    else:
        with smtplib.SMTP(instellingen["host"], poort, timeout=20) as s:
            s.starttls(context=context)
            s.login(instellingen["gebruiker"], instellingen["wachtwoord"])
            s.send_message(bericht)
    return bericht
