#!/usr/bin/env python3
"""PdfQRSplit pipeline for one PDF. No source-file deletion."""
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
import fitz
from PIL import Image
from pyzbar.pyzbar import decode as decode_barcodes
from scan_pdf_cleaner import remove_blank_pages, crop_pdf_margins

def separators(source, expected):
    matches=[]
    with fitz.open(source) as pdf:
        if pdf.page_count<1: raise ValueError("PDF enthält keine Seiten")
        for i,page in enumerate(pdf):
            pix=page.get_pixmap(matrix=fitz.Matrix(2,2),colorspace=fitz.csRGB,alpha=False)
            image=Image.frombytes("RGB",(pix.width,pix.height),pix.samples)
            # QR only, exact value; irrelevant invoice QR codes must not split.
            from pyzbar.pyzbar import ZBarSymbol
            if any(x.data.decode("utf-8",errors="replace")==expected for x in decode_barcodes(image,symbols=[ZBarSymbol.QRCODE])):
                matches.append(i)
    return matches

def sections(count, markers, keep):
    # Separator starts NEXT document. Leading document preserved.
    result=[]; current=[]
    mark=set(markers)
    for i in range(count):
        if i in mark:
            if current:result.append(current);current=[]
            if keep:current.append(i)
        else:current.append(i)
    if current:result.append(current)
    return result

def run(source, out_dir, qr_text, options):
    source=Path(source).resolve(strict=True)
    target=Path(out_dir).resolve()
    target.mkdir(parents=True,exist_ok=True)
    if source.suffix.lower()!=".pdf":raise ValueError("Nur PDF-Dateien")
    if not qr_text:raise ValueError("QR-Text fehlt")
    with fitz.open(source) as pdf:
        count=pdf.page_count
    markers=separators(source,qr_text) if options["qr_split"] else []
    groups=sections(count,markers,not options["remove_separators"]) if options["qr_split"] else [list(range(count))]
    if not groups:raise ValueError("Alle Seiten wären Trennblätter; Ausgabe verweigert")
    generated=[]
    # Stage all outputs privately. Publish only after every subprocess succeeds.
    with tempfile.TemporaryDirectory(prefix="qrscan-",dir=target) as scratch:
        temp=Path(scratch)
        for index,pages in enumerate(groups,1):
            draft=temp/f"part-{index:04}.pdf"
            with fitz.open(source) as doc:
                sub=fitz.open()
                for number in pages:sub.insert_pdf(doc,from_page=number,to_page=number)
                sub.save(draft)
            current=draft
            if options["remove_blank"]:
                cleaned=temp/f"clean-{index:04}.pdf"
                # Conservative ink allowance: 0.5% of page pixels
                retained,removed=remove_blank_pages(str(current),str(cleaned),threshold=0.5)
                current=cleaned
            if options["crop"]:
                cropped=temp/f"crop-{index:04}.pdf"
                # Upstream implementation applies a fixed crop box, not automatic content detection.
                crop_pdf_margins(str(current),str(cropped),margin_pt=12)
                current=cropped
            if options["ocr"]:
                ocr=temp/f"ocr-{index:04}.pdf"
                cmd=["ocrmypdf","-l",options.get("languages","deu+eng"),"--skip-text","--output-type",options.get("output_type","pdf"),str(current),str(ocr)]
                if options.get("rotate_pages"):cmd.insert(-2,"--rotate-pages")
                if options.get("deskew"):cmd.insert(-2,"--deskew")
                subprocess.run(cmd,check=True,timeout=900,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                current=ocr
            final=target/f"{source.stem}_{index:04}.pdf"
            if final.exists():raise FileExistsError(f"Ausgabedatei bereits vorhanden: {final}")
            staged=temp/f"publish-{index:04}.pdf"
            staged.write_bytes(current.read_bytes())
            generated.append((staged,final))
        # Prevent overwrite if a file appeared during processing.
        published=[]
        try:
            for staged,final in generated:
                fd=os.open(final,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o640)
                published.append(final)
                with os.fdopen(fd,"wb") as stream:stream.write(staged.read_bytes());stream.flush();os.fsync(stream.fileno())
        except Exception:
            for f in published:f.unlink(missing_ok=True)
            raise
    return {"source":str(source),"qr_pages":[x+1 for x in markers],"outputs":[str(f) for _,f in generated]}

def main():
    p=argparse.ArgumentParser(description="QR-Code basierte PDF-Verarbeitung für einen Einzelauftrag")
    p.add_argument("source");p.add_argument("output_dir");p.add_argument("--qr-text",default="SCAN-TRENNUNG-001")
    p.add_argument("--no-qr-split",action="store_true")
    p.add_argument("--remove-separators",action="store_true")
    p.add_argument("--remove-blank",action="store_true")
    p.add_argument("--crop",action="store_true")
    p.add_argument("--ocr",action="store_true")
    p.add_argument("--languages",default="deu+eng")
    p.add_argument("--output-type",choices=["pdf","pdfa"],default="pdf")
    p.add_argument("--rotate-pages",action="store_true")
    p.add_argument("--deskew",action="store_true")
    args=p.parse_args()
    opts=dict(qr_split=not args.no_qr_split,remove_separators=args.remove_separators,remove_blank=args.remove_blank,crop=args.crop,ocr=args.ocr,languages=args.languages,output_type=args.output_type,rotate_pages=args.rotate_pages,deskew=args.deskew)
    print(json.dumps(run(args.source,args.output_dir,args.qr_text,opts),ensure_ascii=False))
if __name__=="__main__":main()
