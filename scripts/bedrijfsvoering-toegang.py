"""Uitvoeren in Authentik Django-shell na app-registreren.py bedrijfsvoering.

Alleen gekoppelde, actieve interne collega's krijgen de appgroep. Dit geeft
geen bedrijfs- of dossiermandaat. Bestaande groepen blijven behouden.
"""
import json
from pathlib import Path
from authentik.core.models import Group, User

config = json.loads(Path('/tmp/bedrijfsvoering-access.json').read_text())
group = Group.objects.get(name='bedrijfsvoering')
owner = User.objects.get(uuid=config['owner_sub'], username='mehdi', is_active=True, type='internal')
eligible = {str(owner.uuid): owner}
missing = 0
for person in config['people']:
    user = User.objects.filter(uuid=person['sub'], is_active=True, type='internal').first()
    if user is None or not user.email:
        missing += 1
        continue
    eligible[str(user.uuid)] = user
added = 0
for user in eligible.values():
    if not user.ak_groups.filter(pk=group.pk).exists():
        user.ak_groups.add(group)
        added += 1
print('BEDRIJFSVOERING_ACCESS:' + json.dumps({'eligible': len(eligible), 'added': added, 'missing_or_without_email': missing, 'business_memberships_granted': 0}))
