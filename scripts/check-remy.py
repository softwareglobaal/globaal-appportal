from authentik.core.models import Application
a = Application.objects.filter(slug="remy").first()
if not a:
    print("NO_REMY_APP"); raise SystemExit
print("name:", a.name)
print("meta_launch_url:", repr(a.meta_launch_url))
try:
    print("launch_url:", repr(a.get_launch_url()))
except Exception as e:
    print("launch_url ERROR:", e)
p = a.provider
print("provider:", p, "| external_host:", repr(getattr(p, "external_host", None)))
print("CHECK_REMY_DONE")
