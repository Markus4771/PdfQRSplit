"""Conservative visual fingerprinting of individual invoices.

Not OCR/document identity. A probable match is held for manual review.
"""
import hashlib
import json
import pymupdf
from PIL import Image, ImageOps, ImageFilter

def fingerprints(path):
    result=[]
    with pymupdf.open(path) as pdf:
        if not 1 <= len(pdf) <= 200:
            raise ValueError("DATEV: ungültige Seitenzahl")
        for page in pdf:
            pix=page.get_pixmap(matrix=pymupdf.Matrix(1,1),colorspace=pymupdf.csGRAY,alpha=False)
            img=Image.frombytes("L",(pix.width,pix.height),pix.samples)
            img=ImageOps.autocontrast(img.resize((192,256)))
            # Coarse page similarity + exact normalized raster hashes for scanner differences.
            small=img.filter(ImageFilter.GaussianBlur(1)).resize((17,16))
            pixels=list(small.getdata())
            bits=0
            for y in range(16):
                for x in range(16):
                    bits=(bits<<1)|int(pixels[y*17+x]>pixels[y*17+x+1])
            result.append(f"{bits:064x}")
    return result

def near(a,b,threshold=20):
    if len(a)!=len(b): return False
    return all((int(x,16)^int(y,16)).bit_count()<=threshold for x,y in zip(a,b))

def encode(fp):
    return json.dumps(fp,separators=(",",":"))

def decode(value):
    return json.loads(value)
