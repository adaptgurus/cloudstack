import copy
import unittest

from inspect_labels import CRITICAL, validate


class LabelGateTest(unittest.TestCase):
    def test_missing_appliance_or_firstboot_fallback_rejected(self):
        report = {'applianceSelinuxRelabelAvailable': True, 'autorelabelExists': False,
                  'selinuxConfig': 'enforcing', 'files': {
                      path: {'label': 'system_u:object_r:' + kind + ':s0\x00'} for path, kind in CRITICAL.items()}}
        validate(report)
        for key, value in [('applianceSelinuxRelabelAvailable', False), ('autorelabelExists', True), ('selinuxConfig', 'permissive')]:
            bad = copy.deepcopy(report)
            bad[key] = value
            with self.assertRaises(ValueError):
                validate(bad)
        for label in ['', 'system_u:object_r:unlabeled_t:s0', 'system_u:object_r:bin_t:s0']:
            bad = copy.deepcopy(report)
            bad['files']['/usr/lib64/ld-linux-x86-64.so.2']['label'] = label
            with self.assertRaises(ValueError):
                validate(bad)

    def test_preflight_is_capability_only(self):
        validate({'preflight': True, 'applianceSelinuxRelabelAvailable': True})
        with self.assertRaises(ValueError):
            validate({'preflight': True, 'applianceSelinuxRelabelAvailable': False})
