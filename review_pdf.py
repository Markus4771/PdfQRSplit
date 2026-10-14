"""Read-only, path-restricted preview and offline PDF correction drafts."""
import hashlib
import json
import os
from pathlib import Path

def source_for_case(con,signature,share_root,archive_root):
    if len(signature)!=64 or any(ch not in "0123456789abcdef" for ch in signature):
        raise ValueError("Ungültige Auftragskennung")
    row=con.execute("""SELECT j.file,j.details FROM jobs j
        JOIN company_profile_links l ON l.profile_id=j.profile_id WHERE j.signature=?""",(signature,)).fetchone()
    if not row:raise ValueError("Prüfauftrag nicht vorhanden")
    try:details=json.loads(row[1] or "{}")
    except (ValueError,TypeError):details={}
    candidates=[row[0]]
    if isinstance(details,dict) and isinstance(details.get("original_archive"),str):
        candidates.append(details["original_archive"])
    allowed=[Path(share_root).resolve(),Path(archive_root).resolve()]
    for entry in candidates:
        path=Path(entry)
        try:
            resolved=path.resolve(strict=True)
            if (resolved.is_file() and resolved.suffix.lower()==".pdf"
                    and any(resolved.is_relative_to(root) for root in allowed)
                    and not path.is_symlink()):
                return resolved
        except (OSError,ValueError):
            pass
    raise FileNotFoundError("Original-PDF derzeit nicht verfügbar. Bitte Original aus Scanner/Archiv prüfen.")

def prepare_draft(con,signature,root,share_root,archive_root,pages,rotation):
    import fitz
    if rotation not in (0,90,180,270):raise ValueError("Ungültige Drehung")
    src=source_for_case(con,signature,share_root,archive_root)
    destination=Path(root).resolve()
    destination.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(destination,0o700)
    with fitz.open(src) as doc:
        if doc.needs_pass:raise ValueError("Passwortgeschütztes PDF")
        if doc.page_count<1 or doc.page_count>3000:raise ValueError("Unzulässige Seitenzahl")
        if not pages.strip():numbers=list(range(doc.page_count))
        else:
            numbers=[]
            for part in pages.split(","):
                try:number=int(part.strip())
                except ValueError:raise ValueError("Seiten als Nummern mit Komma angeben")
                if number<1 or number>doc.page_count or number in numbers:
                    raise ValueError("Seite ungültig oder doppelt")
                numbers.append(number-1)
            if not numbers or len(numbers)>3000:raise ValueError("Keine gültigen Seiten")
        draft=fitz.open()
        for number in numbers:
            draft.insert_pdf(doc,from_page=number,to_page=number)
            page=draft[-1]
            page.set_rotation((page.rotation+rotation)%360)
        target=destination/(signature+".pdf")
        import tempfile
        fd,tmp=tempfile.mkstemp(prefix=".draft-",suffix=".pdf",dir=destination)
        os.close(fd)
        try:
            draft.save(tmp,garbage=3,deflate=True)
            os.chmod(tmp,0o600)
            os.replace(tmp,target)
        finally:
            Path(tmp).unlink(missing_ok=True)
        draft.close()
    return target
