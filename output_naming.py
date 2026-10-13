"""Collision-safe output naming for new and manually replayed jobs."""
from pathlib import Path

def output_stem(source_stem, destination, digest, replay_count=0):
    """Reserve original name when available, otherwise select unique stable job name.

    The PDF publisher still enforces atomic, no-overwrite semantics. A name
    reserved by a previous attempt is not silently reused.
    """
    if replay_count:
        return f"{source_stem}_wiederholung_{digest[:12]}_{replay_count}"
    original = Path(destination) / f"{source_stem}_0001.pdf"
    if original.exists() or original.is_symlink():
        return f"{source_stem}_neu_{digest[:12]}"
    return source_stem
