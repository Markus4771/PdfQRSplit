"""Regression checks: verified archive, no overwrite, source retention on failure."""
import tempfile
import unittest
from pathlib import Path
from original_archive import file_hash,prepare_archive,remove_archived_source

class ArchiveTests(unittest.TestCase):
    def test_archive_then_clear_input(self):
        with tempfile.TemporaryDirectory() as work:
            base=Path(work)
            src=base/"invoice.pdf"
            src.write_bytes(b"%PDF-1.4 archive test")
            checksum=file_hash(src)
            archived,before=prepare_archive(src,base/"private",checksum)
            self.assertTrue(src.exists())
            self.assertEqual(Path(archived).read_bytes(),src.read_bytes())
            remove_archived_source(src,archived,checksum,before)
            self.assertFalse(src.exists())
            self.assertTrue(Path(archived).exists())
    def test_modified_source_not_removed(self):
        with tempfile.TemporaryDirectory() as work:
            base=Path(work);src=base/"invoice.pdf"
            src.write_bytes(b"original")
            digest=file_hash(src)
            archived,before=prepare_archive(src,base/"private",digest)
            src.write_bytes(b"changed content")
            with self.assertRaises(ValueError):
                remove_archived_source(src,archived,digest,before)
            self.assertTrue(src.exists())
    def test_wrong_digest_cannot_archive(self):
        with tempfile.TemporaryDirectory() as work:
            base=Path(work);src=base/"invoice.pdf";src.write_bytes(b"source")
            with self.assertRaises(ValueError):
                prepare_archive(src,base/"private","0"*64)
            self.assertTrue(src.exists())
    def test_archive_is_idempotent(self):
        with tempfile.TemporaryDirectory() as work:
            base=Path(work);src=base/"invoice.pdf";src.write_bytes(b"source")
            digest=file_hash(src)
            first,_=prepare_archive(src,base/"private",digest)
            second,_=prepare_archive(src,base/"private",digest)
            self.assertEqual(first,second)
if __name__=="__main__":unittest.main()
