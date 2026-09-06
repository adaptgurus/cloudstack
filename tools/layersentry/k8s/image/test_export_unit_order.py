"""Exercise real systemd ordering semantics with exact Rocky cloud-final ordering."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ExportUnitOrdering(unittest.TestCase):
    @unittest.skipUnless(shutil.which('systemd-analyze'), 'native systemd verifier unavailable')
    def test_export_does_not_hold_multi_user_before_cloud_final(self):
        source = Path(__file__).with_name('customize_guest.sh').read_text()
        unit = source.split("<<'UNIT'\n", 1)[1].split('\nUNIT', 1)[0]
        # Native graph verification executes no service. Replace only the
        # executable path to avoid requiring guest programs on the test host.
        unit = unit.replace('ExecStart=/usr/bin/python3 /usr/local/libexec/layersentry-export-host-public-key', 'ExecStart=/bin/true')
        declared = next(line.split('=', 1)[1] for line in unit.splitlines() if line.startswith('WantedBy='))
        # cloud-init-24.4-8.el9_8.1.rocky.0.1: cloud-final is After=multi-user,
        # installed into cloud-init.target. These are the causal vendor edges.
        units = {
            'cloud-final.service': '[Unit]\nAfter=multi-user.target\n[Service]\nType=oneshot\nExecStart=/bin/true\n',
            'cloud-init.target': '[Unit]\nAfter=multi-user.target\n',
            'multi-user.target': '[Unit]\nRequires=basic.target\nAfter=basic.target\n',
            'basic.target': '[Unit]\nDefaultDependencies=no\n',
            'sysinit.target': '[Unit]\nDefaultDependencies=no\n',
            'shutdown.target': '[Unit]\nDefaultDependencies=no\n',
            'sshd-keygen.target': '[Unit]\nDescription=SSH keygen fixture\n',
            'boot-test.target': '[Unit]\nWants=multi-user.target cloud-init.target\nAfter=multi-user.target cloud-init.target\n',
            'layersentry-host-public-key.service': unit,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in units.items():
                (root / name).write_text(content)
            for target in ['cloud-init.target', 'multi-user.target']:
                (root / (target + '.wants')).mkdir()
            (root / 'cloud-init.target.wants/cloud-final.service').symlink_to('../cloud-final.service')
            for target, cycle in [('multi-user.target', True), (declared, False)]:
                link = root / (target + '.wants/layersentry-host-public-key.service')
                link.symlink_to('../layersentry-host-public-key.service')
                result = subprocess.run(['systemd-analyze', 'verify', '--man=no', 'boot-test.target'],
                                        env=dict(os.environ, SYSTEMD_UNIT_PATH=str(root)),
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
                link.unlink()
                self.assertEqual(0, result.returncode, result.stdout)
                self.assertEqual(cycle, 'ordering cycle' in result.stdout.lower(), result.stdout)
