#!/bin/sh
# Beperkt SSH-account voor Ashvand, zelfde patroon als scripts/sufa-namen. Door de
# beheerder te draaien, vanuit ~/appportal/spil-test/root:
#   sudo sh install.sh "ssh-ed25519 AAAA... ashvand-spil"
# Idempotent; opnieuw draaien met een andere sleutel vervangt de sleutel.
set -eu

sleutel="${1:-}"
case "$sleutel" in
  ssh-ed25519\ *) ;;
  *) echo "Geef de publieke sleutel mee, tussen aanhalingstekens (ssh-ed25519 ...)"; exit 1 ;;
esac
case "$sleutel" in
  *[!A-Za-z0-9+/=\ @._-]*) echo "De sleutel bevat tekens die er niet in horen"; exit 1 ;;
esac

cd "$(dirname "$0")"

install -o root -g root -m 0755 spil-ctl /usr/local/sbin/spil-ctl
install -o root -g root -m 0755 spil-shell /usr/local/bin/spil-shell
visudo -cf spil-test-sudoers
install -o root -g root -m 0440 spil-test-sudoers /etc/sudoers.d/spil-test

id ashvand >/dev/null 2>&1 || useradd -m -s /bin/sh ashvand
chmod 750 /home/ashvand
# ~/.ssh is van root, zodat hij zijn eigen sleutelbestand niet kan wijzigen.
mkdir -p /home/ashvand/.ssh
chown root:root /home/ashvand/.ssh
chmod 755 /home/ashvand/.ssh
printf 'restrict,command="/usr/local/bin/spil-shell" %s\n' "$sleutel" > /home/ashvand/.ssh/authorized_keys
chown root:root /home/ashvand/.ssh/authorized_keys
chmod 644 /home/ashvand/.ssh/authorized_keys

echo "Klaar. Test: ssh ashvand@54.80.98.233 status"
