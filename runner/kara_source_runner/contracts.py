"""Shared, side-effect-free validation for the API and local Runner."""
import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit, urlunsplit


def https_url(value):
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ValueError('invalid_https_url')
    try:
        p = urlsplit(value)
        port = p.port
        if (p.scheme != 'https' or not p.hostname or p.username is not None or p.password is not None
                or p.query or p.fragment or any(c.isspace() or ord(c) < 32 or c in '\\%' for c in value)):
            raise ValueError()
        host = p.hostname.encode('idna').decode().lower()
        host = '[' + host + ']' if ':' in host else host
        if port and port != 443:
            host += ':' + str(port)
        parts = p.path.split('/')
        if any(x in ('.', '..') for x in parts) or '//' in p.path:
            raise ValueError()
        return urlunsplit(('https', host, p.path.rstrip('/'), '', ''))
    except (ValueError, UnicodeError):
        raise ValueError('invalid_https_url') from None


def repository_url(value):
    value = https_url(value)
    p = urlsplit(value)
    if len(p.path.strip('/').split('/')) < 2 or '/-/' in p.path:
        raise ValueError('repository_clone_url_required')
    return value if value.endswith('.git') else value + '.git'


def repository_on_connection(repository, origin):
    repository, origin = repository_url(repository), https_url(origin)
    a, b = urlsplit(repository), urlsplit(origin)
    prefix = b.path.rstrip('/') + '/'
    if a.netloc != b.netloc or not a.path.startswith(prefix) or len(a.path[len(prefix):].split('/')) < 2:
        raise ValueError('repository_connection_mismatch')
    return repository


def branch_name(value):
    if (not isinstance(value, str) or not value or len(value) > 200 or value == '@'
            or value.startswith(('-', '/')) or value.endswith(('/', '.')) or '..' in value or '@{' in value
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c in '~^:?*[\\' for c in value)
            or any(not part or part.startswith('.') or part.endswith('.lock') for part in value.split('/'))):
        raise ValueError('invalid_branch')
    return value


def relative_path(value, *, markdown=False):
    if (not isinstance(value, str) or not value or len(value) > 240 or '\\' in value
            or PurePosixPath(value).is_absolute() or any(not (c.isalnum() or c in '-_./') for c in value)
            or any(not part or part.startswith('.') for part in value.split('/'))
            or len(value.split('/')) > 8 or (markdown and not value.lower().endswith('.md'))):
        raise ValueError('invalid_relative_path')
    return value


def workspace_files(components, documents):
    if not isinstance(components, list) or not 1 <= len(components) <= 8:
        raise ValueError('one_to_eight_components_required')
    if not isinstance(documents, list) or len(documents) > 16:
        raise ValueError('too_many_documents')
    paths, keys = [], set()
    for part in components:
        if not isinstance(part, dict) or not isinstance(part.get('key'), str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', part['key']):
            raise ValueError('invalid_component_key')
        if part['key'] in keys:
            raise ValueError('duplicate_component_key')
        keys.add(part['key'])
        paths.append(relative_path(part.get('path')))
    for i, path in enumerate(paths):
        if any(path == other or path.startswith(other + '/') or other.startswith(path + '/') for other in paths[:i]):
            raise ValueError('overlapping_component_paths')
    docs, total = set(), 0
    for doc in documents:
        if not isinstance(doc, dict) or set(doc) != {'path', 'content'} or not isinstance(doc['content'], str) or '\x00' in doc['content']:
            raise ValueError('invalid_document')
        path = relative_path(doc['path'], markdown=True)
        if path in docs or any(path == p or path.startswith(p + '/') or p.startswith(path + '/') for p in [*paths, *docs]):
            raise ValueError('overlapping_document_path')
        docs.add(path)
        size = len(doc['content'].encode())
        total += size
        if size > 65536 or total > 262144:
            raise ValueError('document_budget_exceeded')
    return True
