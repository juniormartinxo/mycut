"""Content-addressed archive (acervo) of the files the horizontal projects use (ADR 0015).

A file is stored once under its SHA-256, outside Git, whatever the number of projects that import it. Projects
reference it from their editing document and their history; a file is only deleted by a cleanup the author asks
for, and only when nothing references it any more.
"""
import hashlib
import os
import tempfile
import threading
import time
from .config import DATA, UPLOAD_LIMIT

FOLDER = DATA / 'resources'
# Imports and cleanups of the API process take turns, so a cleanup never deletes a file an import is referencing.
LOCK = threading.Lock()
MEDIA = ('image/', 'video/', 'audio/')


def path(digest):
    return FOLDER / digest[:2] / digest


def media_type(declared):
    """Only media are served with their own type; anything else is downloaded as bytes."""
    declared = (declared or '').split(';')[0].strip().lower()
    return declared if declared.startswith(MEDIA) and len(declared) <= 100 else 'application/octet-stream'


def keep(db, stream, declared):
    """Store the content once; returns its hash, size and whether this call created the file."""
    incoming = FOLDER / '.incoming'
    incoming.mkdir(parents=True, exist_ok=True)
    digest, size = hashlib.sha256(), 0
    with tempfile.NamedTemporaryFile(dir=incoming, delete=False) as temp:
        try:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > UPLOAD_LIMIT:
                    raise ValueError('Use arquivos de até 100 MB.')
                digest.update(chunk)
                temp.write(chunk)
        except BaseException:
            os.unlink(temp.name)
            raise
    if size == 0:
        os.unlink(temp.name)
        raise ValueError('O arquivo está vazio.')
    digest = digest.hexdigest()
    target = path(digest)
    created = not target.is_file()
    if created:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp.name, target)
    else:
        os.unlink(temp.name)
    db.execute('INSERT OR IGNORE INTO resources VALUES(?,?,?,?)', (digest, size, media_type(declared), time.time()))
    return digest, size, created


def forget(db, digests):
    """Drop the rows of contents that nothing references; returns the bytes freed and the files to delete once
    the transaction commits, so a rollback never leaves a row without its file."""
    freed, paths = 0, []
    for digest in digests:
        row = db.execute('SELECT size FROM resources WHERE hash=?', (digest,)).fetchone()
        if row is None:
            continue
        db.execute('DELETE FROM resources WHERE hash=?', (digest,))
        paths.append(path(digest))
        freed += row['size']
    return freed, paths
