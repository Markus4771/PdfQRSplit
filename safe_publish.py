"""Safe publication of completed PDF files.

Stage PDFs in a private directory on the destination filesystem. No final filename
is visible until its complete data is flushed; never overwrite existing output.
"""
import os
from pathlib import Path

def publish(generated, destination):
    """Publish sequence of (staged Path, final Path); rollback on ordinary errors."""
    destination=Path(destination)
    for staged,final in generated:
        if final.parent!=destination or final.exists():
            raise FileExistsError(str(final))
        if not staged.is_file() or staged.stat().st_size==0:
            raise ValueError("Empty or missing output: "+str(staged))
    reserved=[]
    published=[]
    try:
        # Hard links provide no-overwrite semantics and expose only complete files.
        # Source staging files and destination must be on the same filesystem.
        for staged,final in generated:
            os.link(staged,final,follow_symlinks=False)
            reserved.append(final)
            published.append(final)
        dirfd=os.open(destination,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(dirfd)
        finally:os.close(dirfd)
    except BaseException:
        for path in reserved:
            try:path.unlink()
            except OSError:pass
        raise
    return published
