"""Read-only conversion of JPEG/PNG scan inputs to a temporary PDF."""
from pathlib import Path

IMAGE_EXTENSIONS={".jpg",".jpeg",".png"}

def image_to_pdf(source,destination):
    import fitz
    from PIL import Image,UnidentifiedImageError
    source=Path(source)
    destination=Path(destination)
    if source.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("Nur JPEG/PNG werden als Fotos akzeptiert")
    if source.stat().st_size>100*1024*1024:
        raise ValueError("Bilddatei zu groß")
    try:
        with Image.open(source) as image:
            image.verify()
        with Image.open(source) as image:
            if image.width*image.height>100_000_000:
                raise ValueError("Bildabmessungen zu groß")
        with fitz.open(source) as image_doc:
            pdf_bytes=image_doc.convert_to_pdf()
        with fitz.open("pdf",pdf_bytes) as pdf:
            if pdf.page_count!=1:raise ValueError("Foto muss eine Seite enthalten")
            pdf.save(destination)
    except (UnidentifiedImageError,OSError,RuntimeError) as exc:
        raise ValueError("Bilddatei beschädigt oder nicht lesbar") from exc
    return destination
