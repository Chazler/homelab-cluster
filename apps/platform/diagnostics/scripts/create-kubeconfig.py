#!/usr/bin/env python3
"""Run with an administrator's current context; never copy its user credentials."""
import argparse
import json
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
parser.add_argument('--duration', default='8h')
args = parser.parse_args()
os.umask(0o077)

def kubectl(*arguments):
    return subprocess.check_output(['kubectl', *arguments], text=True)

source = json.loads(kubectl('config', 'view', '--minify', '--flatten', '--raw', '-o', 'json'))
cluster = source['clusters'][0]['cluster']
if cluster.get('insecure-skip-tls-verify') or not cluster.get('certificate-authority-data'):
    raise SystemExit('A verified cluster CA is required.')
# Request a temporary token using the current administrator identity.
token = kubectl('-n', 'diagnostics', 'create', 'token', 'codex-diagnostics',
                '--duration', args.duration).strip()
config = {
    'apiVersion': 'v1', 'kind': 'Config',
    'clusters': [{'name': 'homelab', 'cluster': {
        'server': cluster['server'],
        'certificate-authority-data': cluster['certificate-authority-data'],
    }}],
    'users': [{'name': 'codex-diagnostics', 'user': {'token': token}}],
    'contexts': [{'name': 'homelab-diagnostics', 'context': {
        'cluster': 'homelab', 'user': 'codex-diagnostics', 'namespace': 'jellyfin',
    }}],
    'current-context': 'homelab-diagnostics',
}
# Exclusive creation avoids overwriting an existing administrator kubeconfig.
with args.output.open('x') as output:
    json.dump(config, output, indent=2)
    output.write('\n')
print(f'Created {args.output}; token lifetime is controlled by the API server.')
