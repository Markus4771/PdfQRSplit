"""Regression tests for safe output publication (no PDF dependencies required)."""
import tempfile
import unittest
from pathlib import Path
from safe_publish import publish

class PublishTest(unittest.TestCase):
    def test_publish_completed_files(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"stage";stage.mkdir()
            a=stage/"a.pdf";b=stage/"b.pdf"
            a.write_bytes(b"%PDF-1.4\na");b.write_bytes(b"%PDF-1.4\nb")
            finals=[root/"a.pdf",root/"b.pdf"]
            publish([(a,finals[0]),(b,finals[1])],root)
            self.assertEqual(finals[0].read_bytes(),a.read_bytes())
            self.assertEqual(finals[1].read_bytes(),b.read_bytes())
    def test_existing_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"stage";stage.mkdir()
            a=stage/"new.pdf";a.write_bytes(b"new")
            target=root/"original.pdf";target.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                publish([(a,target)],root)
            self.assertEqual(target.read_bytes(),b"existing")
    def test_empty_output_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);stage=root/"stage";stage.mkdir()
            a=stage/"empty.pdf";a.touch()
            with self.assertRaises(ValueError):
                publish([(a,root/"empty.pdf")],root)
            self.assertFalse((root/"empty.pdf").exists())

if __name__=="__main__":unittest.main()
