import importlib.util
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

FORGE = Path(__file__).resolve().parents[1] / "forge"
import sys
sys.path.insert(0, str(FORGE))
from standalone_brain import build

spec = importlib.util.spec_from_file_location("package_runtime", FORGE / "package_runtime.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackageRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        brain = self.root / "source.json"
        brain.write_text(json.dumps({"instructions": [
            {"text": "Retain source references and verify invoices.",
             "sources": [{"path": "a.md"}]}],
            "quality_quarantine": [], "requires_review": []}), encoding="utf-8")
        self.db = self.root / "golden_dragon.sqlite"
        build(brain, self.db)
        self.output = self.root / "bundle.zip"

    def tearDown(self):
        self.temp.cleanup()

    def test_package_contains_independent_skill_and_runtime(self):
        report = package.package(self.db, self.output)
        self.assertTrue(report["integrity_verified"])
        self.assertTrue(package.verify(self.output)["passed"])
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(set(archive.namelist()), {
                "golden_dragon.py", "golden_dragon.sqlite",
                "SKILL.md", "README.md", "manifest.json"})
            self.assertIn(b"Golden Dragon", archive.read("SKILL.md"))
        with self.assertRaises(FileExistsError):
            package.package(self.db, self.output)

    def test_changed_content_fails_digest_check(self):
        package.package(self.db, self.output)
        modified = self.root / "modified.zip"
        with zipfile.ZipFile(self.output, "r") as first, zipfile.ZipFile(modified, "w") as second:
            for item in first.namelist():
                data = first.read(item)
                if item == "README.md":
                    data += b" extra unverified content"
                second.writestr(item, data)
        result = package.verify(modified)
        self.assertFalse(result["passed"])
        self.assertIn("Digest mismatch", result["reason"])

    def test_extracted_runtime_verify_detects_tampering(self):
        from golden_dragon_runtime import verify_install
        package.package(self.db, self.output)
        extracted = self.root / "installed"
        with zipfile.ZipFile(self.output, "r") as archive:
            archive.extractall(extracted)
        self.assertTrue(verify_install(extracted)["passed"])
        readme = extracted / "README.md"
        readme.write_bytes(readme.read_bytes() + b"tamper")
        finding = verify_install(extracted)
        self.assertFalse(finding["passed"])
        self.assertEqual(finding["failures"][0]["file"], "README.md")


if __name__ == "__main__":
    unittest.main()
