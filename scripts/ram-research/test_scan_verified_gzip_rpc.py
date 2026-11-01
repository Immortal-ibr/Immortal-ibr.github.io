import gzip
import hashlib
import tempfile
import unittest
from pathlib import Path

from scan_verified_gzip import scan_archive_in_memory


class VerifiedGzipRpcTests(unittest.TestCase):
    def test_cli_rpc_adapter_accepts_synthetic_completed_item(self):
        event = (
            b'{"method":"item/completed","params":{"threadId":"thread-1",'
            b'"turnId":"turn-1","item":{"type":"agentMessage",'
            b'"id":"item-1","text":"synthetic answer","phase":"final_answer"}}}'
        )
        raw = b"\0" * 64 + event + b"\0" * 64
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "memory.raw.gz"
            with gzip.open(archive, "wb") as target:
                target.write(raw)
            result, digest = scan_archive_in_memory(
                archive,
                [{"Virtual": 0, "Physical": 0, "Size": len(raw)}],
                len(raw),
                hashlib.sha256(raw).hexdigest(),
                "cli-rpc",
            )
        self.assertEqual(digest.lower(), hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["unique_complete_records"], 1)
        self.assertEqual(result["records"][0]["payload"]["method"], "item/completed")
        self.assertEqual(result["records"][0]["payload"]["params"]["item"]["id"], "item-1")

    def test_cli_rpc_adapter_rejects_wrong_raw_digest(self):
        raw = b'{"method":"item/completed","params":{}}'
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "memory.raw.gz"
            with gzip.open(archive, "wb") as target:
                target.write(raw)
            with self.assertRaisesRegex(ValueError, "does not match the acquisition"):
                scan_archive_in_memory(
                    archive,
                    [{"Virtual": 0, "Physical": 0, "Size": len(raw)}],
                    len(raw),
                    "0" * 64,
                    "cli-rpc",
                )


if __name__ == "__main__":
    unittest.main()
