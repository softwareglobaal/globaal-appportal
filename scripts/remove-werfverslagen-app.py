"""Tegel Werfverslagen uit de Authentik-bibliotheek halen (Mehdi 28-10-2026: één tegel voor werfverslagen).

Werfverslag (werf.globaal.be, apps.yaml) blijft de enige tegel. De bordpagina mijnagents.globaal.be/werfverslagen blijft
bestaan en is voor beheerders bereikbaar via het menu-item Werfverslagen in de werfapp (globaal-werfverslag
app/templates/base.html, /werfgroep). Deze tegel was een koppeling zonder eigen provider (scripts/add-werfverslagen-app.py),
dus er hangt niets anders aan; de groepskoppelingen (PolicyBinding) gaan mee weg.

Draaien op de VM:   sh scripts/ak-exec.sh scripts/remove-werfverslagen-app.py
Terugzetten:        sh scripts/ak-exec.sh scripts/add-werfverslagen-app.py
"""
from authentik.core.models import Application

SLUG = "werfverslagen"

app = Application.objects.filter(slug=SLUG).first()
if app is None:
    print("APP:", SLUG, "bestaat niet (al weg)")
elif app.provider_id is not None:
    # Dan is het niet de losse koppeling die we kennen; niets wissen, eerst nakijken.
    print("APP:", SLUG, "heeft een provider; niets verwijderd")
else:
    app.delete()
    print("APP:", SLUG, "verwijderd")
