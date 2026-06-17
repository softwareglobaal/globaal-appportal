from authentik.core.models import Application
a = Application.objects.get(slug="remy")
a.name = "Factuurrouter"
a.save()
print("Naam gewijzigd naar:", a.name, "| slug blijft:", a.slug)
print("RENAME_DONE")
