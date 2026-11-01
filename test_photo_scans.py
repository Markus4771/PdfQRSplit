import tempfile
import unittest
from pathlib import Path
from PIL import Image
from photo_scans import publish_photo

class PhotoScanTests(unittest.TestCase):
    def test_jpeg_png_unchanged_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for fmt,ext in (("JPEG",".jpg"),("PNG",".png")):
                original=root/("input"+ext)
                Image.new("RGB",(20,20),(8,13,21)).save(original,format=fmt)
                before=original.read_bytes()
                result=publish_photo(original,root,"scan"+ext[1:])
                output=Path(result["outputs"][0])
                self.assertEqual(output.read_bytes(),before)
                with self.assertRaises(FileExistsError):
                    publish_photo(original,root,"scan"+ext[1:])
    def test_reject_unsupported_and_corrupt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            bad=root/"corrupt.png"
            bad.write_bytes(b"not an image")
            with self.assertRaises(Exception):
                publish_photo(bad,root,"out")
            txt=root/"scan.txt"
            txt.write_text("hello")
            with self.assertRaises(ValueError):
                publish_photo(txt,root,"out")

if __name__=="__main__":
    unittest.main()
