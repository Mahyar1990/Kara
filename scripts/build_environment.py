"""Private CA inputs shared by host and bootstrap-container build preparation."""
import os
from pathlib import Path


def ca_source():
    from local_dify import ROOT, settings
    configured = settings()['KARA_CA_BUNDLE']
    mounted = os.environ.get('KARA_SETUP_CA')
    if not configured:
        return None
    source = Path(mounted) if mounted else Path(configured).expanduser()
    if not source.is_absolute():
        source = ROOT / source
    return source


def ca_bytes():
    source = ca_source()
    if source is None:
        return b''
    data = source.read_bytes()
    if b'PRIVATE KEY' in data or b'-----BEGIN CERTIFICATE-----' not in data:
        raise ValueError('KARA_CA_BUNDLE must contain PEM certificates only, without private keys')
    return data.rstrip() + b'\n'


def prepare_ca(target):
    target.write_bytes(ca_bytes())


def configure_ca():
    source = ca_source()
    if source is not None:
        ca_bytes()  # Reject missing/malformed bundles before network operations.
        os.environ['SSL_CERT_FILE'] = str(source)
        os.environ['GIT_SSL_CAINFO'] = str(source)
