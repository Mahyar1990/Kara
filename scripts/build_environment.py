"""Private CA inputs shared by host and bootstrap-container build preparation."""
import os
import ssl
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
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # OpenSSL accepts bundle annotations that are not ASCII; do not decode
        # the entire OS trust store as though every byte were a PEM block.
        context.load_verify_locations(cafile=str(source))
    except ssl.SSLError as error:
        raise ValueError('KARA_CA_BUNDLE must contain valid PEM certificates') from error
    return data.rstrip() + b'\n'


def prepare_ca(target):
    target.write_bytes(ca_bytes())


def configure_ca():
    source = ca_source()
    if source is not None:
        ca_bytes()  # Reject missing/malformed bundles before network operations.
        os.environ['SSL_CERT_FILE'] = str(source)
        os.environ['GIT_SSL_CAINFO'] = str(source)
