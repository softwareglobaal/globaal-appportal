#!/usr/bin/env python3
"""Voert de echte groepstoewijzingsbron uit met uitsluitend lokale model-fixtures.

Geen Authentik-installatie, VM, netwerk of echte configuratie wordt benaderd.
"""
from __future__ import annotations

import contextlib
import ast
import io
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = ROOT / "scripts/bedrijfsvoering-toegang.py"
SOURCE = compile(SOURCE_PATH.read_text(), str(SOURCE_PATH), "exec")
OWNER_UUID = "00000000-0000-0000-0000-000000000001"
APP_GROUP = SimpleNamespace(pk=91, name="bedrijfsvoering")


class Query:
    def __init__(self, items):
        self.items = list(items)

    @staticmethod
    def matches(item, key, value):
        if key.endswith("__in"):
            return getattr(item, key[:-4]) in value
        return getattr(item, key) == value

    def filter(self, **criteria):
        return Query(item for item in self.items
                     if all(self.matches(item, key, value) for key, value in criteria.items()))

    def exclude(self, **criteria):
        return Query(item for item in self.items
                     if not all(self.matches(item, key, value) for key, value in criteria.items()))

    def get(self, **criteria):
        items = self.filter(**criteria).items
        if len(items) != 1:
            raise LookupError("Geen eenduidige fixture voor de gecontroleerde eigenaar.")
        return items[0]

    def first(self):
        return self.items[0] if self.items else None

    def exists(self):
        return bool(self.items)

    def __iter__(self):
        return iter(self.items)


class Memberships:
    def __init__(self, existing=()):
        self.ids = set(existing)
        self.add_calls = 0

    def filter(self, **criteria):
        return Query(SimpleNamespace(pk=pk) for pk in self.ids).filter(**criteria)

    def add(self, group):
        self.add_calls += 1
        self.ids.add(group.pk)


def person(number, username, *, active=True, kind="internal", email=None, groups=()):
    return SimpleNamespace(
        uuid=f"00000000-0000-0000-0000-{number:012d}",
        username=username,
        is_active=active,
        type=kind,
        email=email if email is not None else f"{username}@example.test",
        ak_groups=Memberships(groups),
    )


def run_access(users, config=None):
    config = config if config is not None else {"owner_sub": OWNER_UUID, "people": []}
    models = ModuleType("authentik.core.models")
    models.User = SimpleNamespace(objects=Query(users))
    models.Group = SimpleNamespace(objects=Query([APP_GROUP]))
    auth_package = ModuleType("authentik")
    auth_package.__path__ = []
    core_package = ModuleType("authentik.core")
    core_package.__path__ = []
    modules = {"authentik": auth_package, "authentik.core": core_package,
               "authentik.core.models": models}
    def fixture_read(path, *args, **kwargs):
        if str(path) == "/tmp/bedrijfsvoering-access.json":
            return json.dumps(config)
        raise AssertionError(f"Onverwachte configuratielezing: {path}")

    output = io.StringIO()
    with patch.dict(sys.modules, modules), patch.object(Path, "read_text", fixture_read), \
            contextlib.redirect_stdout(output):
        exec(SOURCE, {"__name__": "bedrijfsvoering_access_fixture"})
    lines = output.getvalue().splitlines()
    if len(lines) != 1 or not lines[0].startswith("BEDRIJFSVOERING_ACCESS:"):
        raise AssertionError("Toegangsscript moet uitsluitend het resultaatoverzicht afdrukken.")
    return json.loads(lines[0].split(":", 1)[1])


class BedrijfsvoeringToegang(unittest.TestCase):
    def assert_unassigned(self, users):
        for user in users:
            self.assertNotIn(APP_GROUP.pk, user.ak_groups.ids, user.username)
            self.assertEqual(user.ak_groups.add_calls, 0, user.username)

    def test_active_internal_colleagues_without_kern_links_get_only_app_group(self):
        owner = person(1, "mehdi")
        colleague = person(2, "collega", groups=[17])
        other_colleague = person(3, "anderecollega")
        summary = run_access([owner, colleague, other_colleague])
        self.assertEqual(summary["eligible"], 3)
        self.assertEqual(summary["added"], 3)
        self.assertEqual(summary["business_memberships_granted"], 0)
        self.assertEqual(owner.ak_groups.ids, {APP_GROUP.pk})
        self.assertEqual(colleague.ak_groups.ids, {17, APP_GROUP.pk})
        self.assertEqual(other_colleague.ak_groups.ids, {APP_GROUP.pk})

    def test_excluded_accounts_stay_out_even_when_central_profiles_reference_them(self):
        owner = person(1, "mehdi")
        excluded = [
            person(2, "AnonymousUser"),
            person(3, "akadmin"),
            person(4, "servicerunner", kind="service_account"),
            person(5, "externe", kind="external"),
            person(6, "uitdienst", active=False),
        ]
        config = {"owner_sub": OWNER_UUID,
                  "people": [{"sub": user.uuid, "username": user.username} for user in excluded]}
        summary = run_access([owner, *excluded], config)
        self.assertEqual(summary["eligible"], 1)
        self.assertEqual(summary["added"], 1)
        self.assertEqual(summary["business_memberships_granted"], 0)
        self.assertEqual(summary["linked_profiles_missing_or_ineligible"], len(excluded))
        self.assert_unassigned(excluded)

    def test_active_colleagues_without_email_get_app_access_and_are_not_missing(self):
        owner = person(1, "mehdi")
        without_email = person(2, "zonderemail", email="")
        without_email_field = person(3, "zondermailveld")
        del without_email_field.email
        config = {"owner_sub": OWNER_UUID, "people": [
            {"sub": without_email.uuid, "username": without_email.username},
            {"sub": without_email_field.uuid, "username": without_email_field.username},
            {"sub": person(99, "onbekend").uuid, "username": "onbekend"},
        ]}
        summary = run_access([owner, without_email, without_email_field], config)
        self.assertEqual(summary["eligible"], 3)
        self.assertEqual(summary["added"], 3)
        self.assertEqual(summary["linked_profiles_missing_or_ineligible"], 1)
        self.assertEqual(summary["business_memberships_granted"], 0)
        self.assertEqual(without_email.ak_groups.ids, {APP_GROUP.pk})
        self.assertEqual(without_email_field.ak_groups.ids, {APP_GROUP.pk})

    def test_repeated_execution_is_idempotent_and_preserves_other_groups(self):
        owner = person(1, "mehdi", groups=[11])
        colleague = person(2, "collega", groups=[12, 13])
        users = [owner, colleague]
        first = run_access(users)
        second = run_access(users)
        self.assertEqual(first["added"], 2)
        self.assertEqual(second["added"], 0)
        self.assertEqual(owner.ak_groups.ids, {11, APP_GROUP.pk})
        self.assertEqual(colleague.ak_groups.ids, {12, 13, APP_GROUP.pk})
        self.assertEqual(owner.ak_groups.add_calls, 1)
        self.assertEqual(colleague.ak_groups.add_calls, 1)

    def test_preexisting_app_membership_is_not_added_again(self):
        owner = person(1, "mehdi", groups=[APP_GROUP.pk, 11])
        colleague = person(2, "collega", groups=[APP_GROUP.pk])
        summary = run_access([owner, colleague])
        self.assertEqual(summary["added"], 0)
        self.assertEqual(owner.ak_groups.ids, {APP_GROUP.pk, 11})
        self.assertEqual(owner.ak_groups.add_calls, 0)
        self.assertEqual(colleague.ak_groups.add_calls, 0)

    def test_owner_requires_exact_uuid_without_username_fallback(self):
        owner = person(1, "mehdi")
        colleague = person(2, "collega")
        with self.assertRaises(LookupError):
            run_access([owner, colleague], {"owner_sub": person(99, "onbekend").uuid, "people": []})
        self.assert_unassigned([owner, colleague])

    def test_owner_uuid_cannot_point_to_another_username(self):
        owner = person(1, "mehdi")
        colleague = person(2, "collega")
        with self.assertRaises(LookupError):
            run_access([owner, colleague], {"owner_sub": colleague.uuid, "people": []})
        self.assert_unassigned([owner, colleague])

    def test_inactive_or_non_internal_owner_blocks_all_assignments(self):
        for attributes in ({"active": False}, {"kind": "service_account"}, {"kind": "external"}):
            with self.subTest(attributes=attributes):
                owner = person(1, "mehdi", **attributes)
                colleague = person(2, "collega")
                with self.assertRaises(LookupError):
                    run_access([owner, colleague])
                self.assert_unassigned([owner, colleague])

    def test_exact_verified_owner_without_email_is_eligible(self):
        owner = person(1, "mehdi", email="")
        colleague = person(2, "collega")
        summary = run_access([owner, colleague])
        self.assertEqual(summary["eligible"], 2)
        self.assertEqual(summary["added"], 2)
        self.assertEqual(summary["business_memberships_granted"], 0)
        self.assertEqual(owner.ak_groups.ids, {APP_GROUP.pk})

    def test_configuration_owner_probe_accepts_exact_active_internal_identity_without_email(self):
        tree = ast.parse((ROOT / "scripts/bedrijfsvoering-configureren.py").read_text())
        assignment = next(node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == "code"
                                  for target in node.targets))
        expression = ast.Expression(body=assignment.value)
        probe = eval(compile(expression, "configuration_owner_probe", "eval"),
                     {"owner": [{"sub": OWNER_UUID}]})
        owner = person(1, "mehdi", email="")
        owner.uid = "0" * 64
        models = ModuleType("authentik.core.models")
        models.User = SimpleNamespace(objects=Query([owner]))
        output = io.StringIO()
        with patch.dict(sys.modules, {"authentik.core.models": models}), \
                contextlib.redirect_stdout(output):
            exec(probe, {})
        summary = json.loads(output.getvalue().strip().split(":", 1)[1])
        self.assertEqual(summary, {"owner_uid": owner.uid})

    def test_directory_and_linked_profile_do_not_duplicate_assignment(self):
        owner = person(1, "mehdi")
        colleague = person(2, "collega")
        config = {"owner_sub": OWNER_UUID, "people": [
            {"sub": owner.uuid, "username": owner.username},
            {"sub": colleague.uuid, "username": "oudegebruikersnaam"},
            {"sub": colleague.uuid, "username": colleague.username},
        ]}
        summary = run_access([owner, colleague], config)
        self.assertEqual(summary["eligible"], 2)
        self.assertEqual(summary["added"], 2)
        self.assertEqual(colleague.ak_groups.add_calls, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
