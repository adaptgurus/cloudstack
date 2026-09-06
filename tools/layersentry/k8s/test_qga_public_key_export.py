"""Confined QGA public-export reader checks; no guest/host operation."""
import contextlib
import io
import json
import os
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bootstrap.transport import _GUEST_PUBLIC_KEY


class PublicExportTests(unittest.TestCase):
    def read(self, *, parent=None, file=None, content='ssh-ed25519 AAAA root@guest\n', open_error=None):
        directory=SimpleNamespace(st_mode=stat.S_IFDIR|0o755,st_uid=0,st_gid=0)
        regular=SimpleNamespace(st_mode=stat.S_IFREG|0o644,st_uid=0,st_gid=0,st_nlink=1,st_size=len(content))
        directory.__dict__.update(parent or {});regular.__dict__.update(file or {})
        output=io.StringIO()
        with patch('os.lstat',return_value=directory),patch('os.open',return_value=77,side_effect=open_error) as opened,patch('os.fstat',return_value=regular),patch('os.fdopen',return_value=io.StringIO(content)),patch('os.close') as closed,contextlib.redirect_stdout(output):
            exec(_GUEST_PUBLIC_KEY,{})
            opened.assert_called_once_with('/usr/share/layersentry/node-image/ssh_host_ed25519_key.pub',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            closed.assert_called_once_with(77)
        return json.loads(output.getvalue())

    def test_only_fixed_public_export_is_read(self):
        self.assertEqual(self.read(),{'hostKey':'ssh-ed25519 AAAA root@guest'})
        self.assertNotIn("'/etc/ssh/",_GUEST_PUBLIC_KEY)

    def test_nonroot_writable_or_linked_parent_is_rejected(self):
        for parent in ({'st_uid':1000},{'st_gid':1000},{'st_mode':stat.S_IFDIR|0o777},{'st_mode':stat.S_IFLNK|0o777}):
            with self.subTest(parent=parent),self.assertRaises(SystemExit):self.read(parent=parent)

    def test_unsafe_export_metadata_is_rejected(self):
        for file in ({'st_uid':1000},{'st_gid':1000},{'st_nlink':2},{'st_mode':stat.S_IFREG|0o666},{'st_mode':stat.S_IFIFO|0o644},{'st_size':4097},{'st_size':0}):
            with self.subTest(file=file),self.assertRaises(SystemExit):self.read(file=file)

    def test_missing_symlink_or_multiline_export_has_no_fallback(self):
        for error in (FileNotFoundError(),OSError('no-follow')):
            with self.subTest(error=type(error).__name__),self.assertRaises(OSError):self.read(open_error=error)
        with self.assertRaises(SystemExit):self.read(content='ssh-ed25519 AAAA\nssh-ed25519 BBBB\n')


if __name__=='__main__':unittest.main()
