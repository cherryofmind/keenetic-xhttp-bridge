import importlib.util
from pathlib import Path
import unittest
import uuid

spec = importlib.util.spec_from_file_location('audit', Path(__file__).parents[1] / 'tools/audit_public.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class PublicationBoundary(unittest.TestCase):
    def test_private_file_rejected_even_if_force_added(self):
        self.assertTrue(m.findings('generated/router.json', '{}'))
        self.assertTrue(m.findings('site.local.json', '{}'))
        self.assertTrue(m.findings('domains.local.txt', 'private.example.org'))

    def test_actual_uuid_rejected(self):
        self.assertTrue(m.findings('README.md', str(uuid.uuid4())))

    def test_private_key_block_rejected(self):
        value = '-----BEGIN ' + 'PRIVATE KEY-----'
        self.assertTrue(m.findings('notes.txt', value))

    def test_deny_list_match_does_not_print_secret(self):
        self.assertEqual(m.findings('notes.txt', 'hidden-value', ['hidden-value']), ['explicit private deny-list match'])

    def test_documentation_addresses_and_dns_accepted(self):
        self.assertEqual(m.findings('example.json', '198.51.100.10 203.0.113.20 192.168.1.1 77.88.8.8'), [])

    def test_real_host_rejected(self):
        address = '.'.join(['93', '184', '216', '34'])
        self.assertIn('real public host address', m.findings('notes.txt', address))


if __name__ == '__main__': unittest.main()
