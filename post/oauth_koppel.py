"""Koppel een Microsoft-mailbox eenmalig aan de Postbus (device-code-login).

Draaien in de container, met het adres zoals het in mailboxen.yaml staat
(met auth: microsoft en een oauth_client_id):

    docker exec -it appportal-app-post-1 python oauth_koppel.py <adres>

Het script vraagt Microsoft om een koppelcode en toont een adres plus code.
De eigenaar van de mailbox opent dat adres, vult de code in, logt in en geeft
toestemming. Daarna bewaart het script het refresh token in
POSTBUS_OAUTH_MAP/<adres>.json en test het meteen een echte IMAP-login.
Opnieuw draaien vervangt de koppeling; dat is ook de weg als hij ooit
verloopt of wordt ingetrokken.
"""
import sys
import time

import config
import imapbron
import oauth_ms


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    gevraagd = sys.argv[1].strip().lower()
    mailboxen, fouten = config.alles()
    mailbox = next((m for m in mailboxen if m["adres"].lower() == gevraagd),
                   None)
    if not mailbox:
        print(f"{gevraagd} staat niet (goed) in mailboxen.yaml.")
        for f in fouten:
            if gevraagd in f.lower():
                print("  " + f)
        sys.exit(1)
    if mailbox.get("auth") != "microsoft":
        print(f"{gevraagd} staat niet op auth: microsoft; koppelen is niet nodig.")
        sys.exit(1)

    antwoord = oauth_ms.post(oauth_ms.DEVICE_URL, {
        "client_id": mailbox["oauth_client_id"], "scope": oauth_ms.SCOPE})
    if "device_code" not in antwoord:
        print("Koppelcode aanvragen mislukt: "
              f"{antwoord.get('error')}: {antwoord.get('error_description')}")
        sys.exit(1)

    print()
    print(f"  Open:  {antwoord['verification_uri']}")
    print(f"  Code:  {antwoord['user_code']}")
    print(f"  Log in als {mailbox['adres']} en geef toestemming.")
    print(f"  (geldig {int(antwoord.get('expires_in', 900)) // 60} minuten)")
    print(flush=True)

    interval = int(antwoord.get("interval", 5))
    einde = time.time() + int(antwoord.get("expires_in", 900))
    while time.time() < einde:
        time.sleep(interval)
        token = oauth_ms.post(oauth_ms.TOKEN_URL, {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": mailbox["oauth_client_id"],
            "device_code": antwoord["device_code"],
        })
        fout = token.get("error")
        if fout == "authorization_pending":
            continue
        if fout == "slow_down":
            interval += 5
            continue
        if fout:
            print(f"Koppelen mislukt: {fout}: "
                  f"{str(token.get('error_description', ''))[:300]}")
            sys.exit(1)
        if not token.get("refresh_token"):
            print("Microsoft gaf geen refresh token terug; staat offline_access "
                  "bij de API permissions van de app-registratie?")
            sys.exit(1)
        # Wat Microsoft echt toestond, niet wat we vroegen: geeft de eigenaar
        # geen toestemming voor versturen, dan leest deze koppeling alleen.
        toegestaan = str(token.get("scope", ""))
        scope = (oauth_ms.SCOPE if "SMTP.Send" in toegestaan
                 else oauth_ms.SCOPE_ALLEEN_IMAP)
        oauth_ms.bewaar(mailbox["adres"], {
            "refresh_token": token["refresh_token"],
            "scope": scope,
            "gekoppeld_op": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        print("Gekoppeld, token bewaard. Versturen toegestaan: "
              + ("ja" if scope == oauth_ms.SCOPE else "nee (alleen lezen)"))
        print("Nu een echte IMAP-login testen...")
        break
    else:
        print("De code is verlopen zonder login. Draai het script opnieuw.")
        sys.exit(1)

    try:
        uit = imapbron.mappen(mailbox)
    except Exception as e:
        print(f"IMAP-login mislukt: {type(e).__name__}: {e}")
        sys.exit(1)
    print(f"IMAP-login OK: {len(uit['alle_mappen'])} mappen, "
          f"waaronder {', '.join(uit['alle_mappen'][:5])}")


if __name__ == "__main__":
    main()
