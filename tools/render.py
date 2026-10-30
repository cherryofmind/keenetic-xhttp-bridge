#!/usr/bin/env python3
"""Generate fresh local profiles. Never connects, installs or changes routing."""
import argparse
import copy
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
from urllib.parse import quote, urlencode
import uuid

ROOT = Path(__file__).resolve().parents[1]


def required(value):
    if not isinstance(value, str) or not value or 'REPLACE' in value:
        raise ValueError('Fill every local credential field or use the init command')
    return value


def host(value):
    value = required(value)
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        if len(value) > 253 or not re.fullmatch(r'[a-zA-Z0-9.-]+', value):
            raise ValueError('Invalid host name') from None
        return value


def clean_settings(s):
    s = copy.deepcopy(s)
    for name in ('entry', 'exit'):
        n = s[name]
        n['host'] = host(n['host'])
        if not isinstance(n['port'], int) or not 1024 <= n['port'] <= 65535:
            raise ValueError('Reference services use unprivileged ports 1024..65535')
        n['id'] = str(uuid.UUID(required(n['id'])))
    e, x = s['entry'], s['exit']
    for field in ('encryption', 'decryption'):
        if not required(e[field]).startswith('mlkem768x25519plus.'):
            raise ValueError('The XHTTP entry requires VLESS Encryption; none is rejected')
    if not re.fullmatch(r'/[A-Za-z0-9/_-]{8,160}', required(e['path'])):
        raise ValueError('Use a long random XHTTP path beginning with /')
    for field in ('private_key', 'public_key'):
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', required(x[field])):
            raise ValueError('Expected a base64url X25519 value from xray x25519')
    if not re.fullmatch(r'[0-9a-fA-F]{16}', required(x['short_id'])):
        raise ValueError('short_id must contain 16 hexadecimal characters')
    x['server_name'] = host(x['server_name'])
    if not isinstance(s.get('router_mips_receive_buffer', False), bool):
        raise ValueError('router_mips_receive_buffer must be a boolean')
    return s


def lines(path):
    return [v.strip() for v in Path(path).read_text(encoding='utf-8-sig').splitlines()
            if v.strip() and not v.lstrip().startswith('#')]


def profiles(settings, domains, ips):
    s = clean_settings(settings)
    e, x = s['entry'], s['exit']
    for d in domains:
        if not re.fullmatch(r'[A-Za-z0-9.-]+', d):
            raise ValueError('Custom domains must be ASCII or punycode names, without URLs')
    ips = [str(ipaddress.ip_network(v, strict=False)) for v in ips]
    direct = {'tag': 'direct', 'protocol': 'freedom'}
    block = {'tag': 'block', 'protocol': 'blackhole'}
    client = {
        'tag': 'vpn', 'protocol': 'vless',
        'settings': {'vnext': [{'address': e['host'], 'port': e['port'], 'users': [
            {'id': e['id'], 'encryption': e['encryption'], 'flow': 'xtls-rprx-vision'}]}]},
        'streamSettings': {'network': 'xhttp', 'security': 'none',
                           'xhttpSettings': {'path': e['path'], 'mode': 'auto'}}}
    upstream = {
        'tag': 'exit', 'protocol': 'vless',
        'settings': {'vnext': [{'address': x['host'], 'port': x['port'], 'users': [
            {'id': x['id'], 'encryption': 'none', 'flow': 'xtls-rprx-vision'}]}]},
        'streamSettings': {'network': 'raw', 'security': 'reality', 'realitySettings': {
            'serverName': x['server_name'], 'fingerprint': 'chrome',
            'password': x['public_key'], 'shortId': x['short_id']}}}
    router_client = copy.deepcopy(client)
    if s.get('router_mips_receive_buffer'):
        router_client['streamSettings']['sockopt'] = {'customSockopt': [{
            'system': 'linux', 'network': 'tcp', 'level': '65535', 'opt': '4098',
            'value': '1048576', 'type': 'int'}]}
    inbound = []
    for tag, network, port in [('redirect', 'tcp', 1181), ('tproxy', 'udp', 1181),
                                ('force-proxy-redirect', 'tcp', 1191),
                                ('force-proxy-tproxy', 'udp', 1191)]:
        v = {'tag': tag, 'listen': '0.0.0.0' if network == 'tcp' else '127.0.0.1',
             'port': port, 'protocol': 'tunnel',
             'settings': {'allowedNetwork': network, 'followRedirect': True},
             'sniffing': {'enabled': True, 'routeOnly': False,
                          'destOverride': ['http', 'tls'] if network == 'tcp' else ['quic']}}
        if network == 'udp':
            v['streamSettings'] = {'sockopt': {'tproxy': 'tproxy'}}
        inbound.append(v)
    rules = [{'type': 'field', 'inboundTag': ['force-proxy-redirect', 'force-proxy-tproxy'],
              'outboundTag': 'vpn'}]
    if ips:
        rules.append({'type': 'field', 'ip': ips, 'outboundTag': 'vpn'})
    if domains:
        rules.append({'type': 'field', 'domain': ['domain:' + d for d in domains],
                      'outboundTag': 'vpn'})
    rules += [
        {'type': 'field', 'domain': ['ext:geosite_zkeen.dat:bypass'], 'outboundTag': 'direct'},
        {'type': 'field', 'domain': ['ext:geosite_refilter.dat:refilter',
          'ext:geosite_zkeen.dat:domains', 'ext:geosite_zkeen.dat:other',
          'ext:geosite_zkeen.dat:youtube'], 'outboundTag': 'vpn'},
        {'type': 'field', 'ip': ['ext:geoip_zkeenip.dat:meta',
          'ext:geoip_zkeenip.dat:telegram', 'ext:geoip_zkeenip.dat:youtube'], 'outboundTag': 'vpn'},
        {'type': 'field', 'network': 'tcp,udp', 'outboundTag': 'direct'}]
    router = {'log': {'loglevel': 'warning'}, 'inbounds': inbound,
              'outbounds': [direct, router_client, block],
              'routing': {'domainStrategy': 'AsIs', 'rules': rules},
              'policy': {'levels': {'0': {'bufferSize': 32, 'connIdle': 300}}}}
    mobile = {'remarks': 'XHTTP bridge', 'log': {'loglevel': 'warning'},
              'inbounds': [{'tag': 'socks', 'listen': '127.0.0.1', 'port': 10808,
                            'protocol': 'socks', 'settings': {'auth': 'noauth', 'udp': True}}],
              'outbounds': [copy.deepcopy(client), direct, block]}
    entry = {'log': {'loglevel': 'warning'}, 'inbounds': [{
        'tag': 'entry', 'listen': '0.0.0.0', 'port': e['port'], 'protocol': 'vless',
        'settings': {'clients': [{'id': e['id'], 'flow': 'xtls-rprx-vision'}],
                     'decryption': e['decryption']},
        'streamSettings': copy.deepcopy(client['streamSettings'])}], 'outbounds': [upstream]}
    exit_config = {'log': {'loglevel': 'warning'}, 'inbounds': [{
        'tag': 'exit-in', 'listen': '0.0.0.0', 'port': x['port'], 'protocol': 'vless',
        'settings': {'clients': [{'id': x['id'], 'flow': 'xtls-rprx-vision'}], 'decryption': 'none'},
        'streamSettings': {'network': 'raw', 'security': 'reality', 'realitySettings': {
            'target': x['server_name'] + ':443', 'serverNames': [x['server_name']],
            'privateKey': x['private_key'], 'shortIds': [x['short_id']]}}}],
        'outbounds': [direct]}
    params = {'encryption': e['encryption'], 'security': 'none', 'type': 'xhttp',
              'path': e['path'], 'mode': 'auto', 'flow': 'xtls-rprx-vision'}
    address = '[' + e['host'] + ']' if ':' in e['host'] else e['host']
    uri = 'vless://' + e['id'] + '@' + address + ':' + str(e['port']) + '?' + urlencode(
        params, quote_via=quote) + '#XHTTP%20bridge'
    return {'router/00-home.json': router, 'server/entry.json': entry,
            'server/exit.json': exit_config, 'mobile/client.json': mobile,
            'mobile/profile.txt': uri}


def write_private(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content + '\n')


def init_settings(args):
    def invoke(command):
        p = subprocess.run([args.xray, command], capture_output=True, text=True, check=True)
        return p.stdout
    v = invoke('vlessenc')
    pair = invoke('x25519')
    def get(pattern, text):
        m = re.search(pattern, text)
        if not m:
            raise ValueError('Unrecognized Xray key output; no credentials were printed')
        return m.group(1)
    s = json.loads((ROOT / 'settings.example.json').read_text(encoding='utf-8'))
    s['entry'].update(host=host(args.entry_host), id=str(uuid.uuid4()),
        path='/' + secrets.token_urlsafe(24),
        encryption=get(r'"encryption"\s*:\s*"([^"\r\n]+)"', v),
        decryption=get(r'"decryption"\s*:\s*"([^"\r\n]+)"', v))
    s['exit'].update(host=host(args.exit_host), id=str(uuid.uuid4()),
        private_key=get(r'PrivateKey:\s*(\S+)', pair),
        public_key=get(r'(?:Password(?:\s*\(PublicKey\))?|PublicKey):\s*(\S+)', pair), short_id=secrets.token_hex(8))
    s['router_mips_receive_buffer'] = args.mips_router
    out = Path(args.output).resolve()
    if out.is_relative_to(ROOT) and not out.name.endswith('.local.json'):
        raise ValueError('Local settings inside the checkout must end in .local.json')
    write_private(out, json.dumps(clean_settings(s), indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init', help='Generate new keys locally using your installed Xray')
    init.add_argument('--xray', required=True)
    init.add_argument('--entry-host', required=True)
    init.add_argument('--exit-host', required=True)
    init.add_argument('--mips-router', action='store_true')
    init.add_argument('--output', default='settings.local.json')
    render = sub.add_parser('render', help='Render local configurations, without deploying them')
    render.add_argument('--settings', default='settings.local.json')
    render.add_argument('--domains', default=str(ROOT / 'configs/custom-domains.example.txt'))
    render.add_argument('--ips', default=str(ROOT / 'configs/custom-ips.example.txt'))
    render.add_argument('--output', default='generated')
    args = p.parse_args()
    try:
        if args.command == 'init':
            init_settings(args)
        else:
            dest = Path(args.output).resolve()
            if dest.exists():
                raise ValueError('Output exists; use a new directory to preserve existing credentials')
            if dest.is_relative_to(ROOT) and not dest.is_relative_to(ROOT / 'generated'):
                raise ValueError('Outputs inside the checkout must be under generated/')
            values = profiles(json.loads(Path(args.settings).read_text(encoding='utf-8-sig')),
                              lines(args.domains), lines(args.ips))
            for name, value in values.items():
                write_private(dest / name, json.dumps(value, indent=2) if isinstance(value, dict) else value)
        print('Local private output written. Nothing was installed or uploaded.')
    except (ValueError, KeyError, FileExistsError, subprocess.CalledProcessError) as e:
        p.exit(2, type(e).__name__ + ': check local settings, paths and Xray version; existing output is preserved.\n')


if __name__ == '__main__':
    main()
