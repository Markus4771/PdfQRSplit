"""Loss-averse archive for successfully processed DATEV scan originals.

Archive and verify the original first. Only remove it from the input folder
after the completed processing job has been committed to SQLite.
"""
import hashlib
import os
import shutil
import tempfile
from pathlib import Path

def identity(st):
    return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)

def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda:stream.read(1024*1024),b""):
            h.update(data)
    return h.hexdigest()

def prepare_archive(source,archive_root,expected_sha256):
    source=Path(source)
    archive_root=Path(archive_root)
    if source.is_symlink() or not source.is_file():
        raise ValueError("Originaldatei nicht mehr sicher verfügbar")
    before=source.stat()
    if file_hash(source)!=expected_sha256:
        raise ValueError("Originaldatei wurde während der Verarbeitung verändert")
    archive_root.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(archive_root,0o700)
    safe_name=source.stem[:80]
    dest=archive_root/(safe_name+"_"+expected_sha256+".pdf")
    if dest.is_symlink():
        raise ValueError("Archivziel ist ein Symlink")
    if dest.exists():
        if file_hash(dest)!=expected_sha256:
            raise ValueError("Archivdatei hat abweichenden Inhalt")
        return str(dest),before
    fd,tmp=tempfile.mkstemp(prefix=".original-",suffix=".tmp",dir=archive_root)
    try:
        with os.fdopen(fd,"wb") as out,source.open("rb") as stream:
            shutil.copyfileobj(stream,out,1024*1024)
            out.flush()
            os.fsync(out.fileno())
        if file_hash(tmp)!=expected_sha256 or identity(source.stat())!=identity(before) or file_hash(source)!=expected_sha256:
            raise ValueError("Originalarchiv: Quelle oder Kopie verändert")
        os.chmod(tmp,0o600)
        os.link(tmp,dest,follow_symlinks=False)
        folderfd=os.open(archive_root,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(folderfd)
        finally:os.close(folderfd)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return str(dest),before

def remove_archived_source(source,archive,expected_sha256,before):
    """Do not remove a modified source or a source lacking a verified archive."""
    source=Path(source)
    archive=Path(archive)
    if source.is_symlink() or not source.is_file():
        raise ValueError("Eingangsdatei fehlt oder ist Symlink")
    if source.stat()!=before or file_hash(source)!=expected_sha256:
        raise ValueError("Eingangsdatei hat sich geändert; nicht entfernen")
    if not archive.is_file() or archive.is_symlink() or file_hash(archive)!=expected_sha256:
        raise ValueError("Archiv nicht verifiziert; Original bleibt erhalten")
    source.unlink()
