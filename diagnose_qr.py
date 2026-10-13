#!/usr/bin/env python3
"""Read-only QR diagnosis for PDF files. Does not create or change output files."""
import argparse
import json
from pathlib import Path
import pymupdf
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol

def diagnose(path,expected):
    matches=[]
    pages=[]
    with pymupdf.open(path) as doc:
        for i,page in enumerate(doc,1):
            pix=page.get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csRGB,alpha=False)
            image=Image.frombytes("RGB",(pix.width,pix.height),pix.samples)
            codes=[item.data.decode("utf-8",errors="replace") for item in decode(image,symbols=[ZBarSymbol.QRCODE])]
            pages.append({"page":i,"qr_count":len(codes),"qr_texts":codes,"matches":expected in codes})
            if expected in codes:matches.append(i)
    return {"file":str(path),"expected":expected,"matching_pages":matches,"pages":pages}

def main():
    p=argparse.ArgumentParser(description="QR-Diagnose ohne Veränderung von PDFs")
    p.add_argument("pdf",type=Path)
    p.add_argument("--qr-text",default="SCAN-TRENNUNG-001")
    args=p.parse_args()
    print(json.dumps(diagnose(args.pdf,args.qr_text),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
