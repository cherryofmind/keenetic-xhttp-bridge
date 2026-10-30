#!/usr/bin/env python3
"""Fail publication/CI for credentials or real public host addresses in tracked files."""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_NAMES = re.compile(r'(?:\.local\.|\.private\.|\.(?:ovpn|pem|key|p12|pfx|pcap|log)$|^generated/)')
PATTERNS = {
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----'),
    'inline VPN key': re.compile('<' + 'key>'),
    'GitHub token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})'),
    'literal client UUID': re.compile(r'\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b'),
    'VLESS encryption material': re.compile(r'mlkem768x25519plus\.(?:native|xorpub|random)\.(?:0rtt|1rtt|[0-9]+s)\.[A-Za-z0-9_-]{40,}'),
    'literal REALITY private key': re.compile(r'"privateKey"\s*:\s*"[A-Za-z0-9_-]{43}"'),
}
ALLOWED_PUBLIC_IPS = {'1.1.1.1', '8.8.8.8', '8.8.4.4', '77.88.8.8', '77.88.8.1'}


def findings(name, text, deny=()):
    out = []
    if FORBIDDEN_NAMES.search(name): out.append('private/generated filename')
    for label, pattern in PATTERNS.items():
        if pattern.search(text): out.append(label)
    for raw in re.findall(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])', text):
        try:
            addr = ipaddress.ip_address(raw)
            if addr.is_global and raw not in ALLOWED_PUBLIC_IPS: out.append('real public host address')
        except ValueError: pass
    if any(value and value in text for value in deny): out.append('explicit private deny-list match')
    return sorted(set(out))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--deny-file', help='Optional JSON string array outside this repository')
    args = p.parse_args()
    deny = json.loads(Path(args.deny_file).read_text(encoding='utf-8')) if args.deny_file else []
    q = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True)
    names = [v for v in q.stdout.decode().split('\x00') if v]
    if not names: raise SystemExit('No tracked files: stage the publication candidate first')
    bad = []
    for name in names:
        f = ROOT / name
        if not f.is_file(): continue
        hit = findings(name, f.read_text(encoding='utf-8'), deny)
        if hit: bad.append((name, hit))
    for name, hit in bad: print(name + ': ' + ', '.join(hit))
    if bad: raise SystemExit(1)
    print('Publication scan passed: %d tracked text files.' % len(names))


if __name__ == '__main__': main()
