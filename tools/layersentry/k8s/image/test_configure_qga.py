import unittest
from configure_qga import BASE, EXTRA, configure


class QgaPolicyTests(unittest.TestCase):
    def original(self):
        return '# package policy\nFILTER_RPC_ARGS="--allow-rpcs=' + ','.join(sorted(BASE)) + '"\nFSFREEZE_HOOK_PATHNAME=/etc/qemu-ga/fsfreeze-hook\n'

    def test_only_two_required_rpcs_added_and_other_settings_preserved(self):
        original = self.original()
        updated = configure(original)
        self.assertEqual(original.replace('"\nFSFREEZE', ',' + ','.join(EXTRA) + '"\nFSFREEZE'), updated)
        self.assertEqual(updated, configure(updated))

    def test_empty_block_duplicate_and_unreviewed_policies_fail(self):
        for policy in ['FILTER_RPC_ARGS="--allow-rpcs="\n', 'FILTER_RPC_ARGS="--block-rpcs="\n',
                       self.original() * 2, self.original().replace('guest-ping,', ''),
                       self.original().replace('guest-ping,', 'guest-file-open,guest-ping,')]:
            with self.assertRaises(ValueError):
                configure(policy)


if __name__ == '__main__':
    unittest.main()
