#!/usr/bin/env python3
"""Eenmalige/additieve configuratie op de VM. Geen geheimen naar stdout."""
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
BASE = ['docker', 'compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.override.yml']


def query(sql):
    result = subprocess.run(BASE + ['exec', '-T', 'postgresql', 'psql', '-U', 'authentik', '-d', 'appportal', '-Atc', sql], check=True, capture_output=True, text=True)
    return json.loads(result.stdout.strip())


def main():
    os.umask(0o077)
    firms = query("SELECT json_agg(json_build_object('id',id,'name',naam,'code',code,'country',land,'active',actief,'registration',coalesce(kbo_nummer,'')) ORDER BY code) FROM kern.firma")
    people = query("SELECT coalesce(json_agg(json_build_object('sub',authentik_sub,'username',authentik_username) ORDER BY authentik_sub),'[]'::json) FROM kern.persoon WHERE in_dienst=true AND authentik_sub IS NOT NULL AND authentik_sub<>''")
    owner = query("SELECT json_agg(json_build_object('sub',authentik_sub,'username',authentik_username)) FROM kern.persoon WHERE lower(voornaam)='mehdi' AND in_dienst=true AND authentik_sub IS NOT NULL")
    if len(owner or []) != 1 or owner[0]['username'] != 'mehdi':
        raise RuntimeError('De eigenaar is niet eenduidig bevestigd door kern.persoon.')
    code = "from authentik.core.models import User; import json; u=User.objects.get(uuid=" + repr(owner[0]['sub']) + "); assert u.username=='mehdi' and u.is_active and u.type=='internal'; print('BEDRIJFSVOERING_META:'+json.dumps({'owner_uid':u.uid}))"
    result = subprocess.run(BASE + ['exec', '-T', 'authentik-server', 'ak', 'shell', '-c', code], check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    lines = [line for line in result.stdout.splitlines() if line.startswith('BEDRIJFSVOERING_META:')]
    if len(lines) != 1:
        raise RuntimeError('Geen eenduidige gecontroleerde Authentik-eigenaar.')
    uid = json.loads(lines[0].split(':', 1)[1])['owner_uid']
    if not re.fullmatch('[a-f0-9]{64}', uid):
        raise RuntimeError('Authentik proxy-UID is ongeldig.')
    config_dir = ROOT / 'bedrijfsvoering-config'
    config_dir.mkdir(mode=0o700, exist_ok=True)
    for name, value in [('company-seed.json', firms), ('access.json', {'owner_sub': owner[0]['sub'], 'people': people})]:
        target = config_dir / name
        if target.exists():
            # Bewaar de eerdere bronmomentopname vóór vervanging.
            backup = config_dir / (name + '.previous')
            if not backup.exists():
                backup.write_bytes(target.read_bytes())
                backup.chmod(0o600)
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        target.chmod(0o600)
    env_path = ROOT / '.env'
    original = env_path.read_text()
    source = original

    def set_once(name, value, strict=False):
        nonlocal source
        found = re.findall(r'^' + re.escape(name) + r'=(.*)$', source, flags=re.M)
        if len(found) > 1:
            raise RuntimeError('Dubbele instelling: ' + name)
        if found:
            if strict and found[0] != value:
                raise RuntimeError('Bestaande instelling verschilt; behoud en beoordeel: ' + name)
            return
        source = source.rstrip('\n') + '\n' + name + '=' + value + '\n'

    set_once('BEDRIJFSVOERING_OWNER_UID', uid, strict=True)
    set_once('BEDRIJFSVOERING_PROXY_SECRET', secrets.token_hex(32))
    configured_secret = re.findall(r'^BEDRIJFSVOERING_PROXY_SECRET=(.*)$', source, flags=re.M)[0].strip('"\'')
    if len(configured_secret) < 32:
        raise RuntimeError('Bestaand proxygeheim is onvoldoende lang; geen wijziging uitgevoerd.')
    existing = re.findall(r'^COMPOSE_FILE=(.*)$', source, flags=re.M)
    if len(existing) > 1:
        raise RuntimeError('Dubbele COMPOSE_FILE-instelling.')
    overlay = 'docker-compose.bedrijfsvoering.yml'
    if existing:
        current = existing[0].strip('"\'')
        if overlay not in current.split(':'):
            source = re.sub(r'^COMPOSE_FILE=.*$', 'COMPOSE_FILE=' + current + ':' + overlay, source, flags=re.M)
    else:
        set_once('COMPOSE_FILE', 'docker-compose.yml:docker-compose.override.yml:' + overlay)
    # Een eerdere .env behouden, beveiligd en buiten git.
    backup = ROOT / '.env.before-bedrijfsvoering'
    if env_path.read_text() != original:
        raise RuntimeError('.env is ondertussen gewijzigd door een andere sessie; opnieuw beoordelen.')
    if not backup.exists():
        backup.write_text(original)
        backup.chmod(0o600)
    with tempfile.NamedTemporaryFile(mode='w', dir=ROOT, prefix='.env.bedrijfsvoering-', delete=False) as temporary:
        temporary.write(source)
        temporary.flush()
        os.fsync(temporary.fileno())
        private_path = temporary.name
    if env_path.read_text() != original:
        raise RuntimeError('.env is ondertussen gewijzigd; private kandidaat behouden en niets vervangen.')
    os.replace(private_path, env_path)
    exclude = ROOT / '.git/info/exclude'
    ignored = exclude.read_text() if exclude.exists() else ''
    for line in ['/bedrijfsvoering/', '/bedrijfsvoering-config/', '/.env.before-bedrijfsvoering']:
        if line not in ignored.splitlines():
            ignored += '\n' + line
    exclude.write_text(ignored.rstrip() + '\n')
    print(json.dumps({'configured': True, 'companies': len(firms), 'active_companies': sum(bool(f['active']) for f in firms), 'linked_staff_profiles': len(people), 'owner_verified': True, 'secret_values_printed': False}))


if __name__ == '__main__':
    main()
