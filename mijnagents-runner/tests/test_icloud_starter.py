#!/usr/bin/env python3
"""macOS-CI: echte productie-starter, fictief script op het vaste root-pad."""
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import tempfile
import unittest


ROOT = Path('/Library/Application Support/iCloudWacht')
SCRIPT = ROOT / 'icloud_wacht.py'
PYTHON = Path('/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3.9')
PROBE = ("import json,os,sys\n"
         "print(json.dumps({'argv': sys.argv, 'env': dict(os.environ), 'file': __file__, 'python': sys.executable}))\n"
         "raise SystemExit(23 if len(sys.argv) == 2 else 0)\n")


def sudo(*args):
    return subprocess.run(['/usr/bin/sudo', '-n', *map(str, args)],
                          capture_output=True, text=True, check=True)


# Deze proef werkt met sudo in een systeemmap: alleen op de wegwerp-runner van GitHub, nooit op een
# echte Mac. De workflow zet beide variabelen; ontbreekt er een, dan slaat de proef over.
OP_CI_RUNNER = os.environ.get('GITHUB_ACTIONS') == 'true' and bool(os.environ.get('ICLOUD_STARTER_BIN'))


@unittest.skipUnless(OP_CI_RUNNER, 'alleen op de macOS-runner van GitHub Actions (sudo in een systeemmap)')
class StarterGedrag(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bin = Path(os.environ['ICLOUD_STARTER_BIN'])
        if not cls.bin.is_file():
            raise RuntimeError('Productiestarter is niet gecompileerd')
        if not PYTHON.is_file():
            raise RuntimeError(f'Vertrouwde Python 3.9 ontbreekt: {PYTHON}')
        if ROOT.exists() or ROOT.is_symlink():
            raise RuntimeError(f'CI-runner heeft al data op {ROOT}; niets overschrijven')
        if ROOT.with_name('iCloudWacht.proef-parkeren').exists():
            raise RuntimeError('CI-runner heeft al een geparkeerde proefmap')
        sudo('/usr/bin/install', '-d', '-o', 'root', '-g', 'wheel', '-m', '755', ROOT)
        cls.addClassCleanup(cls.cleanup_root)
        cls.install_probe()

    @classmethod
    def cleanup_root(cls):
        # Alleen de eigen fictieve testbestanden op de tijdelijke CI-runner.
        parked = ROOT.with_name('iCloudWacht.proef-parkeren')
        if ROOT.is_symlink():
            sudo('/bin/rm', '-f', ROOT)
        if parked.exists() and not ROOT.exists():
            sudo('/bin/mv', parked, ROOT)
        if SCRIPT.is_symlink() or SCRIPT.is_file():
            sudo('/bin/rm', '-f', SCRIPT)
        real = ROOT / 'icloud_wacht.py.proef'
        if real.exists():
            sudo('/bin/rm', '-f', real)
        if ROOT.exists():
            sudo('/bin/chmod', '755', ROOT)
            sudo('/bin/rmdir', ROOT)

    @classmethod
    def install_probe(cls, source=PROBE):
        # De bron staat buiten de vertrouwde map; install maakt een nieuwe root-inode.
        import tempfile
        with tempfile.TemporaryDirectory() as work:
            bron = Path(work) / 'probe.py'
            bron.write_text(source, encoding='utf-8')
            sudo('/usr/bin/install', '-o', 'root', '-g', 'wheel', '-m', '644', bron, SCRIPT)

    def run_starter(self, *args, extra_env=None):
        env = {'HOME': '/tmp/verkeerd', 'PATH': '/tmp/kwaad',
               'PYTHONPATH': '/tmp/kwaad', 'PYTHONHOME': '/tmp/kwaad',
               'MIJNAGENTS_URL': 'https://voorbeeld.invalid',
               'FOTO_EXPORT': '/tmp/kwaad', 'FOTO_STRAAL_M': '0',
               'DROPBOX_LOKAAL': '/tmp/kwaad'}
        env.update(extra_env or {})
        return subprocess.run([str(self.bin), *args], env=env,
                              capture_output=True, text=True, check=False)

    def assert_veilig_geweigerd(self, result):
        self.assertEqual(result.returncode, 78, result.stderr)
        self.assertIn('iCloudWacht:', result.stderr)
        self.assertFalse(result.stdout)

    def test_argumenten_omgeving_en_exitcode(self):
        result = self.run_starter()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['argv'], [str(SCRIPT)])
        self.assertEqual(data['file'], str(SCRIPT))
        self.assertEqual(data['python'], str(PYTHON))
        self.assertEqual(data['env'], {'HOME': str(Path.home()),
                                       'PATH': '/usr/bin:/bin', 'LANG': 'en_US.UTF-8'})
        self.assertFalse(list(ROOT.glob('__pycache__')))
        result = self.run_starter('--taken')
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(json.loads(result.stdout)['argv'], [str(SCRIPT), '--taken'])
        for args in [('--dag',), ('--taken', '--dag')]:
            with self.subTest(args=args):
                result = self.run_starter(*args)
                self.assertEqual(result.returncode, 64)
                self.assertIn('Gebruik:', result.stderr)
                self.assertFalse(result.stdout)

    def test_geharde_handtekening_en_enkel_apple_events(self):
        app = self.bin.parents[2]
        verify = subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(app)],
                                capture_output=True)
        self.assertEqual(verify.returncode, 0, verify.stderr)
        display = subprocess.run(['/usr/bin/codesign', '-d', '--verbose=4', str(app)],
                                 capture_output=True)
        self.assertEqual(display.returncode, 0, display.stderr)
        flags = re.search(rb'^CodeDirectory .*flags=0x[0-9a-fA-F]+\(([^)]*)\)',
                          display.stderr, re.MULTILINE)
        self.assertIsNotNone(flags)
        self.assertIn(b'runtime', flags.group(1).split(b','))
        rechten = subprocess.run(['/usr/bin/codesign', '-d', '--entitlements', ':-', str(app)],
                                 capture_output=True)
        self.assertEqual(rechten.returncode, 0, rechten.stderr)
        self.assertEqual(plistlib.loads(rechten.stdout),
                         {'com.apple.security.automation.apple-events': True})

    def test_dyld_injectie_wordt_voor_main_geblokkeerd(self):
        with tempfile.TemporaryDirectory(prefix='icloud-dyld-', dir='/private/tmp') as work:
            bron = Path(work) / 'inject.c'
            bron.write_text('#include <unistd.h>\n'
                            '__attribute__((constructor)) static void p(void)'
                            '{write(2,"DYLD_PROEF_GELADEN\\n",18);}\n', encoding='utf-8')
            lib = Path(work) / 'inject.dylib'
            subprocess.run(['/usr/bin/cc', '-dynamiclib', str(bron), '-o', str(lib)], check=True)
            # De controle bewijst dat de tijdelijke dylib op deze runner kan laden.
            controlebron = Path(work) / 'controle.c'
            controlebron.write_text('int main(void){return 64;}\n', encoding='utf-8')
            controle = Path(work) / 'controle'
            subprocess.run(['/usr/bin/cc', str(controlebron), '-o', str(controle)], check=True)
            subprocess.run(['/usr/bin/codesign', '-s', '-', str(controle)],
                           check=True, capture_output=True)
            onbeschermd = subprocess.run([str(controle)],
                                        env={**os.environ, 'DYLD_INSERT_LIBRARIES': str(lib)},
                                        capture_output=True, text=True)
            self.assertEqual(onbeschermd.returncode, 64)
            self.assertIn('DYLD_PROEF_GELADEN', onbeschermd.stderr)
            result = self.run_starter('--fout', extra_env={'DYLD_INSERT_LIBRARIES': str(lib)})
            self.assertEqual(result.returncode, 64, result.stderr)
            self.assertIn('Gebruik:', result.stderr)
            self.assertNotIn('DYLD_PROEF_GELADEN', result.stderr)

    def test_symlink_en_schrijfrechten_worden_geweigerd(self):
        sudo('/bin/chmod', '664', SCRIPT)
        try:
            self.assert_veilig_geweigerd(self.run_starter())
        finally:
            sudo('/bin/chmod', '644', SCRIPT)
        sudo('/bin/mv', SCRIPT, ROOT / 'icloud_wacht.py.proef')
        try:
            sudo('/bin/ln', '-s', ROOT / 'icloud_wacht.py.proef', SCRIPT)
            self.assert_veilig_geweigerd(self.run_starter())
        finally:
            sudo('/bin/rm', '-f', SCRIPT)
            sudo('/bin/mv', ROOT / 'icloud_wacht.py.proef', SCRIPT)
        sudo('/bin/chmod', '775', ROOT)
        try:
            self.assert_veilig_geweigerd(self.run_starter())
        finally:
            sudo('/bin/chmod', '755', ROOT)

    def test_script_moet_root_eigen_zijn(self):
        sudo('/usr/sbin/chown', str(os.getuid()), SCRIPT)
        try:
            self.assert_veilig_geweigerd(self.run_starter())
        finally:
            sudo('/usr/sbin/chown', 'root:wheel', SCRIPT)

    def test_signaalstatus_wordt_doorgegeven(self):
        self.install_probe('import os,signal\nos.kill(os.getpid(), signal.SIGTERM)\n')
        try:
            self.assertEqual(self.run_starter().returncode, 128 + 15)
        finally:
            self.install_probe()

    def test_map_symlink_wordt_geweigerd(self):
        parked = ROOT.with_name('iCloudWacht.proef-parkeren')
        sudo('/bin/mv', ROOT, parked)
        try:
            sudo('/bin/ln', '-s', parked, ROOT)
            self.assert_veilig_geweigerd(self.run_starter())
        finally:
            sudo('/bin/rm', '-f', ROOT)
            sudo('/bin/mv', parked, ROOT)


if __name__ == '__main__':
    unittest.main()
