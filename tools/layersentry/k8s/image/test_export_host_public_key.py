import base64
import struct
import unittest

from export_host_public_key import public_key


class PublicKeyBoundaryTest(unittest.TestCase):
    def test_only_valid_public_wire_encoding_is_exported_without_comment(self):
        blob = struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 32) + bytes(range(32))
        key = 'ssh-ed25519 ' + base64.b64encode(blob).decode()
        self.assertEqual(key + '\n', public_key(key + ' host-comment\n'))
        for bad in ['-----BEGIN OPENSSH PRIVATE KEY-----', key + '\n' + key,
                    key.replace('ssh-ed25519', 'ssh-rsa', 1), 'ssh-ed25519 AAAA',
                    'ssh-ed25519 %%%', key + '\x00']:
            with self.assertRaises(ValueError):
                public_key(bad)
