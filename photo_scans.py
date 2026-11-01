"""Lossless copying of private JPEG/PNG scans; no conversion or OCR."""
import os
import tempfile
from pathlib import Path
from PIL import Image

EXTENSIONS={".jpg",".jpeg",".png"}

def publish_photo(source,destination,stem):
    source=Path(source)
    destination=Path(destination)
    if source.suffix.lower() not in EXTENSIONS:
        raise ValueError("Unsupported photo format")
    if not source.is_file() or not 0<source.stat().st_size<=100*1024*1024:
        raise ValueError("Invalid photo size")
    with Image.open(source) as im:
        if im.format not in ("JPEG","PNG") or im.width*im.height>100_000_000:
            raise ValueError("Invalid photo image")
        im.verify()
    final=destination/(stem+source.suffix.lower())
    fd,tmp=tempfile.mkstemp(prefix=".qrscan-photo-",dir=destination)
    try:
        with os.fdopen(fd,"wb") as output,source.open("rb") as inp:
            while True:
                chunk=inp.read(1024*1024)
                if not chunk:break
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(tmp,0o660)
        os.link(tmp,final,follow_symlinks=False)
        dirfd=os.open(destination,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(dirfd)
        finally:os.close(dirfd)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return {"outputs":[str(final)],"mode":"private-photo-original"}
