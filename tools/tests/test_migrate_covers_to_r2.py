import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import migrate_covers_to_r2 as m
import r2_staging

PUBLIC = "https://media.example"

PAGE = """---
title: "#110 - Something"
image: "/images/covers/110.png"
participants: ["Paulina"]
---

Body mentions image: "/images/covers/110.png" and must stay.
"""


@mock.patch.object(r2_staging, "R2_PUBLIC_URL", PUBLIC)
class MigrateCoversTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.covers, self.episodes = root / "covers", root / "episodes"
        self.covers.mkdir()
        self.episodes.mkdir()
        (self.covers / "110.png").write_bytes(b"one-ten")
        (self.covers / "logo.png").write_bytes(b"not a cover")
        self.page = self.episodes / "110-something.md"
        self.page.write_text(PAGE, encoding="utf-8")
        (self.episodes / "109-other.md").write_text('---\nimage: "/images/other.png"\n---\n', encoding="utf-8")
        self.key = r2_staging.cover_r2_key(110, b"one-ten")

    def run_migrate(self, **kw):
        return m.migrate(covers_dir=self.covers, episodes_dir=self.episodes, **kw)

    def test_plan_skips_non_episode_files(self):
        self.assertEqual(m.plan_uploads(self.covers),
                         [(self.covers / "110.png", "/images/covers/110.png", self.key)])

    def test_dry_run_touches_nothing(self):
        with mock.patch.object(r2_staging, "_r2_s3_client") as client:
            self.assertEqual(self.run_migrate(dry_run=True), 0)
        client.assert_not_called()
        self.assertEqual(self.page.read_text(encoding="utf-8"), PAGE)

    def test_uploads_then_rewrites_front_matter_only(self):
        s3 = mock.Mock()
        s3.get_bucket_lifecycle_configuration.return_value = {"Rules": []}
        with mock.patch.object(r2_staging, "_r2_s3_client", return_value=s3), \
                mock.patch.object(r2_staging, "r2_object_exists", return_value=False):
            self.assertEqual(self.run_migrate(), 0)
        s3.upload_file.assert_called_once()
        text = self.page.read_text(encoding="utf-8")
        self.assertIn(f'image: "{PUBLIC}/{self.key}"\nparticipants', text)
        self.assertIn('Body mentions image: "/images/covers/110.png"', text)
        self.assertIn("/images/other.png", (self.episodes / "109-other.md").read_text(encoding="utf-8"))

    def test_lifecycle_risk_stops_before_upload(self):
        s3 = mock.Mock()
        s3.get_bucket_lifecycle_configuration.return_value = {
            "Rules": [{"ID": "all", "Status": "Enabled", "Expiration": {"Days": 1}, "Filter": {}}]}
        with mock.patch.object(r2_staging, "_r2_s3_client", return_value=s3):
            self.assertEqual(self.run_migrate(), 1)
        s3.upload_file.assert_not_called()
        self.assertEqual(self.page.read_text(encoding="utf-8"), PAGE)


if __name__ == "__main__":
    unittest.main()
