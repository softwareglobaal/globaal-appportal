"""Opgemaakte meldingsmail voor een aanvraag die via een website binnenkwam.

Waarom deze module hier staat en niet in de website: de mail moet een knop
bevatten die rechtstreeks de Pipedrive-deal opent. Het dealnummer bestaat pas
nadat aanvraag_verwerk.py de deal heeft aangemaakt, dus moet de mail ook van
hieruit vertrekken. De sales-collega ziet zo één ongelezen bericht in de inbox
en klikt van daaruit door naar het dossier.

Afspraak over alle eigen sites: een ingevuld webformulier komt binnen als een
opgemaakte mail in de huisstijl van de firma, nooit als kale tekst. Vaste
opbouw: logo bovenaan op een grijze achtergrond, een witte kaart, per veld het
label in de merkkleur met het antwoord eronder, en onderaan "Verzonden vanaf".

E-mailclients (Outlook voorop) negeren <style>-blokken en moderne CSS. Daarom
tabellen voor de opbouw en alle stijl inline. Het logo staat als absolute URL
met een alt-tekst, zodat er iets leesbaars staat als afbeeldingen geblokkeerd
zijn. Er gaat altijd ook een platte-tekstversie mee.
"""
import html
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from urllib.parse import urlsplit, parse_qs
from zoneinfo import ZoneInfo

GRIJS = "#eceded"
INKT = "#1f1f33"
TEKST = "#474747"
ZACHT = "#9a9a9a"
LIJN = "#e8e8e8"

# Per firma de merknaam, de huisstijl en het Pipedrive-bedrijfsdomein.
# Het logo moet PNG of JPG zijn: Outlook toont geen webp.
FIRMAS = {
    "unabo-site": {
        "naam": "UNABO",
        "pipedrive": "unabo",
        "domein": "unabo.be",
        "kleur": "#7272ff",
        "logo": "https://unabo.be/unabo-logo.png",
        "logo_breedte": 235,
    },
    "tkn-site": {
        "naam": "TKN-Buro",
        "pipedrive": "tkn-buro-tekenwerk",
        "domein": "tkn-buro.be",
        "kleur": "#1f3a5f",
        "logo": "",
        "logo_breedte": 0,
    },
}
STANDAARD = FIRMAS["unabo-site"]


def firma(bron: str) -> dict:
    return FIRMAS.get((bron or "").strip().lower(), STANDAARD)


def dealadres(bron: str, deal_id) -> str:
    """Het webadres van de deal, of leeg zonder dealnummer."""
    if not deal_id:
        return ""
    return f"https://{firma(bron)['pipedrive']}.pipedrive.com/deal/{deal_id}"


def _v(waarde) -> str:
    """Tekst veilig in HTML zetten; aanvragen komen van buiten."""
    return html.escape("" if waarde is None else str(waarde), quote=True)


def onderwerp(a: dict) -> str:
    """Ook de sleutel waarmee de mail later in de Pipedrive-inbox wordt
    teruggevonden. Niet wijzigen zonder koppel_mails na te kijken."""
    diensten = a.get("diensten") or []
    dienst = diensten[0] if diensten else "Offerteaanvraag"
    wie = (a.get("adres") or "").strip() or f"{a.get('voornaam','')} {a.get('achternaam','')}".strip()
    return f"Offerteaanvraag {dienst}" + (f" · {wie}" if wie else "")


def _moment(a: dict) -> str:
    try:
        t = datetime.fromisoformat(str(a.get("tijdstip", "")).replace("Z", "+00:00"))
    except ValueError:
        t = datetime.now(timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(ZoneInfo("Europe/Brussels")).strftime("%d-%m-%Y om %H:%M")


def _herkomst(a: dict):
    """(pagina zonder trackingparameters, herkomst) uit de URL van het formulier."""
    url = str(a.get("pagina") or "")
    try:
        delen = urlsplit(url)
    except ValueError:
        return url, ""
    q = parse_qs(delen.query)
    bron = ""
    if "gclid" in q or "gbraid" in q or "wbraid" in q or "gad_source" in q:
        bron = "Google Ads"
    elif q.get("utm_source"):
        bron = q["utm_source"][0]
    schoon = f"{delen.netloc}{delen.path}" if delen.netloc else url
    return schoon, bron


def velden(a: dict) -> list:
    """(label, waarde, link) in de volgorde waarin sales ze nodig heeft."""
    naam = f"{a.get('voornaam','')} {a.get('achternaam','')}".strip()
    email = (a.get("email") or "").strip()
    tel = re.sub(r"[^\d+]", "", str(a.get("telefoon") or ""))
    pagina, herkomst = _herkomst(a)
    bijlagen = a.get("bijlagen") or []
    if isinstance(bijlagen, list):
        bijlagen = ", ".join(str(b.get("naam", b)) if isinstance(b, dict) else str(b) for b in bijlagen)
    return [
        ("Gevraagde diensten", ", ".join(a.get("diensten") or []), ""),
        ("Naam", naam, ""),
        ("E-mail", email, f"mailto:{email}" if email else ""),
        ("Telefoon", a.get("telefoon"), f"tel:{tel}" if tel else ""),
        ("Adres van het project", a.get("adres"), ""),
        ("Type gebouw", a.get("gebouwtype"), ""),
        ("Aard van de werken", a.get("type_aanvraag"), ""),
        ("Bericht van de klant", a.get("omschrijving"), ""),
        ("Bijlagen (apart gemaild)", bijlagen, ""),
        ("Gevonden via", a.get("gevonden_via"), ""),
        ("Herkomst", herkomst, ""),
        ("Ingevuld op pagina", pagina, ""),
        ("Ingediend op", _moment(a), ""),
    ]


def als_tekst(a: dict, deal_url: str = "") -> str:
    regels = []
    if deal_url:
        regels += [f"Deal in Pipedrive: {deal_url}", ""]
    for label, waarde, _ in velden(a):
        if waarde and str(waarde).strip():
            regels += [f"{label}:", str(waarde), ""]
    return "\n".join(regels).rstrip() + "\n"


def als_html(a: dict, deal_url: str = "") -> str:
    f = firma(a.get("bron", ""))
    kleur = f["kleur"]

    rijen = "".join(
        f'<tr><td style="padding:18px 0 0 0;border-bottom:1px solid {LIJN};">'
        f'<div style="font:600 13px/1.4 Arial,Helvetica,sans-serif;color:{kleur};margin-bottom:6px;">{_v(label)}</div>'
        f'<div style="font:400 15px/1.6 Arial,Helvetica,sans-serif;color:{TEKST};padding-bottom:16px;white-space:pre-wrap;">'
        + (f'<a href="{_v(link)}" style="color:{INKT};text-decoration:none;">{_v(waarde)}</a>' if link else _v(waarde))
        + '</div></td></tr>'
        for label, waarde, link in velden(a)
        if waarde and str(waarde).strip()
    )

    if f["logo"]:
        kop = (f'<img src="{_v(f["logo"])}" alt="{_v(f["naam"])}" width="{f["logo_breedte"]}" '
               f'style="display:block;border:0;width:{f["logo_breedte"]}px;max-width:70%;height:auto;">')
    else:
        kop = (f'<div style="font:700 22px/1.2 Arial,Helvetica,sans-serif;color:{kleur};">'
               f'{_v(f["naam"])}</div>')

    # De belangrijkste knop staat bovenaan: de collega moet niet scrollen om
    # bij het dossier te komen.
    knop = ""
    if deal_url:
        knop = (
            f'<tr><td style="padding:22px 0 4px 0;">'
            f'<a href="{_v(deal_url)}" style="display:block;background:{kleur};color:#ffffff;'
            f'font:600 15px/1.2 Arial,Helvetica,sans-serif;text-decoration:none;padding:15px 22px;'
            f'border-radius:8px;text-align:center;">Deze aanvraag behandelen in Pipedrive</a>'
            f'<div style="font:400 12px/1.5 Arial,Helvetica,sans-serif;color:{ZACHT};text-align:center;padding-top:8px;">'
            f'De deal staat al klaar in Pipedrive.</div>'
            f'</td></tr>'
        )

    antwoord = ""
    if a.get("email"):
        antwoord = (
            f'<tr><td style="padding:24px 0 0 0;">'
            f'<a href="mailto:{_v(a["email"])}" style="display:inline-block;background:#ffffff;color:{kleur};'
            f'border:1px solid {kleur};font:600 14px/1.2 Arial,Helvetica,sans-serif;text-decoration:none;'
            f'padding:11px 20px;border-radius:8px;">De klant rechtstreeks antwoorden</a>'
            f'</td></tr>'
        )

    return f"""<!doctype html>
<html lang="nl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_v(onderwerp(a))}</title></head>
<body style="margin:0;padding:0;background:{GRIJS};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{GRIJS};padding:28px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">
        <tr><td align="center" style="padding:8px 0 22px 0;">{kop}</td></tr>
        <tr><td style="background:#ffffff;border-radius:10px;padding:14px 34px 30px 34px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            <tr><td style="padding:14px 0 0 0;font:700 19px/1.35 Arial,Helvetica,sans-serif;color:{INKT};">Nieuwe aanvraag via het contactformulier</td></tr>
            {knop}{rijen}{antwoord}
            <tr><td style="padding:26px 0 0 0;text-align:center;font:400 12px/1.5 Arial,Helvetica,sans-serif;color:{ZACHT};">
              Verzonden vanaf <a href="https://{f['domein']}/" style="color:{ZACHT};">{f['domein']}</a>
            </td></tr>
          </table>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def verstuur(a: dict, deal_id=None, *, instellingen: dict, droog: bool = False):
    """Stuurt de meldingsmail. `instellingen` bevat de SMTP-gegevens.

    Een nieuw bericht komt in de mailbox binnen als ongelezen; koppel_mails in
    aanvraag_verwerk.py houdt het ook in Pipedrive ongelezen.
    """
    url = dealadres(a.get("bron", ""), deal_id)
    f = firma(a.get("bron", ""))
    bericht = EmailMessage()
    bericht["Subject"] = onderwerp(a)
    van = instellingen["van"]
    bericht["From"] = van if "<" in van else f"Website {f['naam']} <{van}>"
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
