import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit, parse_qs
import uuid
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('render', ROOT / 'tools/render.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def settings():
    s = json.loads((ROOT / 'settings.example.json').read_text())
    s['entry'].update(id=str(uuid.UUID(int=1)), encryption='mlkem768x25519plus.native.0rtt.' + 'A' * 43,
                      decryption='mlkem768x25519plus.native.600s.' + 'B' * 43, path='/unit-test-only')
    s['exit'].update(id=str(uuid.UUID(int=2)), private_key='C' * 43, public_key='D' * 43,
                     short_id='0123456789abcdef')
    return s


class Contracts(unittest.TestCase):
    def test_reject_plaintext_entry(self):
        s = settings(); s['entry']['encryption'] = 'none'
        with self.assertRaises(ValueError): m.profiles(s, [], [])

    def test_reject_unfilled_example(self):
        s = json.loads((ROOT / 'settings.example.json').read_text())
        with self.assertRaises(ValueError): m.profiles(s, [], [])

    def test_router_defaults_direct(self):
        c = m.profiles(settings(), [], [])['router/00-home.json']
        self.assertEqual(c['outbounds'][0]['tag'], 'direct')
        self.assertEqual(c['routing']['rules'][-1]['outboundTag'], 'direct')

    def test_manual_destinations_survive_geodata_rules(self):
        c = m.profiles(settings(), ['example.org'], ['203.0.113.7'])['router/00-home.json']
        self.assertEqual(c['routing']['rules'][1]['ip'], ['203.0.113.7/32'])
        self.assertIn('domain:example.org', c['routing']['rules'][2]['domain'])

    def test_redirect_listens_on_lan_while_udp_is_loopback(self):
        c = m.profiles(settings(), [], [])['router/00-home.json']
        by_tag = {v['tag']: v for v in c['inbounds']}
        self.assertEqual(by_tag['redirect']['listen'], '0.0.0.0')
        self.assertEqual(by_tag['tproxy']['listen'], '127.0.0.1')

    def test_mips_socket_options_never_export_to_phone_or_servers(self):
        s = settings(); s['router_mips_receive_buffer'] = True
        values = m.profiles(s, [], [])
        self.assertIn('customSockopt', json.dumps(values['router/00-home.json']))
        for name in ['mobile/client.json', 'server/entry.json', 'server/exit.json']:
            self.assertNotIn('customSockopt', json.dumps(values[name]))

    def test_two_hops_terminate_protocols_without_dnat(self):
        s = settings(); v = m.profiles(s, [], [])
        self.assertEqual(v['server/entry.json']['inbounds'][0]['streamSettings']['network'], 'xhttp')
        self.assertEqual(v['server/entry.json']['outbounds'][0]['streamSettings']['security'], 'reality')
        self.assertEqual(v['server/exit.json']['inbounds'][0]['settings']['clients'][0]['id'], s['exit']['id'])
        self.assertNotEqual(s['entry']['id'], s['exit']['id'])

    def test_uri_roundtrips_encryption_and_path(self):
        s = settings(); uri = m.profiles(s, [], [])['mobile/profile.txt']; q = parse_qs(urlsplit(uri).query)
        self.assertEqual(q['encryption'], [s['entry']['encryption']])
        self.assertEqual(q['path'], [s['entry']['path']])

    def test_no_overwrite_of_private_files(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'output.json'; m.write_private(f, 'first')
            with self.assertRaises(FileExistsError): m.write_private(f, 'second')
            self.assertEqual(f.read_text(), 'first\n')

    def test_settings_not_mutated(self):
        s = settings(); before = copy.deepcopy(s); m.profiles(s, [], [])
        self.assertEqual(s, before)

    def test_init_accepts_current_and_older_x25519_labels(self):
        source = settings()
        for label in ['Password (PublicKey)', 'Password', 'PublicKey']:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as d:
                def run(args, **kwargs):
                    if args[1] == 'vlessenc':
                        return SimpleNamespace(stdout=json.dumps({k: source['entry'][k] for k in ['encryption', 'decryption']}))
                    return SimpleNamespace(stdout='PrivateKey: ' + 'C' * 43 + '\n' + label + ': ' + 'D' * 43 + '\n')
                out = Path(d) / 'site.local.json'
                with patch.object(m.subprocess, 'run', side_effect=run):
                    m.init_settings(SimpleNamespace(xray='mock-xray', entry_host='198.51.100.10',
                        exit_host='203.0.113.20', mips_router=False, output=str(out)))
                self.assertEqual(json.loads(out.read_text())['exit']['public_key'], 'D' * 43)


if __name__ == '__main__': unittest.main()
