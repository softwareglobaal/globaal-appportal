"""Uitvoeren in Authentik Django-shell na app-registreren.py bedrijfsvoering.

Actieve interne Authentik-collega's krijgen de appgroep. Dit geeft
geen bedrijfs- of dossiermandaat. Bestaande groepen blijven behouden.
"""
import json
from pathlib import Path
from authentik.core.models import Group, User

config = json.loads(Path('/tmp/bedrijfsvoering-access.json').read_text())
group = Group.objects.get(name='bedrijfsvoering')
owner = User.objects.get(uuid=config['owner_sub'], username='mehdi', is_active=True, type='internal')
eligible = {str(owner.uuid): owner}
excluded_usernames = ['AnonymousUser', 'akadmin']
# kern.persoon heeft nog onvolledige koppelingen. Voor uitsluitend de apptegel
# is de bestaande Authentik-directory de bron: interne menselijke accounts.
# Systeem-, service-, externe en break-glassaccounts zijn geen collega-login.
for user in User.objects.filter(is_active=True, type='internal').exclude(username__in=excluded_usernames):
    eligible[str(user.uuid)] = user
missing = 0
for person in config['people']:
    user = User.objects.filter(uuid=person['sub'], is_active=True, type='internal').exclude(username__in=excluded_usernames).first()
    if user is None:
        missing += 1
        continue
    eligible[str(user.uuid)] = user
added = 0
for user in eligible.values():
    if not user.ak_groups.filter(pk=group.pk).exists():
        user.ak_groups.add(group)
        added += 1
print('BEDRIJFSVOERING_ACCESS:' + json.dumps({'eligible': len(eligible), 'added': added, 'linked_profiles_missing_or_ineligible': missing, 'business_memberships_granted': 0}))
