import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from prepare_inputs import InputError, ROOT, load_lock, verify_file, unique, ApprovedRedirect
from build_cpu_image import validate_binary_archive, build


class InputContractTest(unittest.TestCase):
    def test_pinned_inputs_cover_universal_host_capabilities(self):
        lock = load_lock(ROOT / 'cpu-rocky9-rke2-lock.json')
        names = [p['file'] for p in lock['rpmPackages']]
        for required in ['cloud-init-', 'qemu-guest-agent-', 'openssh-server-', 'python3-', 'iscsi-initiator-utils-', 'device-mapper-multipath-', 'nvme-cli-', 'nfs-utils-', 'lvm2-', 'mdadm-', 'xfsprogs-', 'e2fsprogs-', 'container-selinux-', 'firewalld-']:
            self.assertTrue(any(name.startswith(required) for name in names), required)
        self.assertEqual(lock['qualificationStatus'], 'NOT_TESTED')

    def test_moving_external_and_path_inputs_are_rejected(self):
        original = load_lock(ROOT / 'cpu-rocky9-rke2-lock.json')
        for field, value in [('url', 'https://127.0.0.1/a.qcow2'), ('url', 'http://download.rockylinux.org/a.qcow2'), ('file', '../base.qcow2'), ('size', True), ('sha256', 'mutable')]:
            lock = copy.deepcopy(original)
            lock['baseImage'][field] = value
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'lock.json'
                path.write_text(json.dumps(lock))
                with self.assertRaises(InputError):
                    load_lock(path)
        with self.assertRaises(InputError):
            unique([('key', 1), ('key', 2)])

    def test_input_corruption_and_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input'
            item = {'file': 'input', 'size': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()}
            path.write_bytes(b'abc')
            verify_file(path, item)
            path.write_bytes(b'bad')
            with self.assertRaises(InputError):
                verify_file(path, item)
            path.unlink()
            path.symlink_to('/etc/passwd')
            with self.assertRaises(InputError):
                verify_file(path, item)

    def test_redirect_cannot_leave_approved_github_cdn(self):
        for url in ['http://release-assets.githubusercontent.com/a', 'https://127.0.0.1/a', 'https://example.com/a']:
            with self.assertRaises(InputError):
                ApprovedRedirect().redirect_request(None, None, 302, '', {}, url)

    def test_archive_traversal_links_and_missing_binary_fail(self):
        for name, member_type in [('../escape', tarfile.REGTYPE), ('/bin/escape', tarfile.REGTYPE), ('bin/link', tarfile.SYMTYPE), ('bin/link', tarfile.LNKTYPE), ('share/only', tarfile.REGTYPE)]:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'rke2.tar.gz'
                with tarfile.open(path, 'w:gz') as archive:
                    member = tarfile.TarInfo(name)
                    member.type = member_type
                    member.linkname = '/etc/passwd'
                    archive.addfile(member, io.BytesIO(b''))
                with self.assertRaises(InputError):
                    validate_binary_archive(path)

    def test_existing_output_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'output'
            output.mkdir()
            (output / 'known-good').write_text('preserve')
            with self.assertRaises(InputError):
                build(root, output)
            self.assertEqual((output / 'known-good').read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
