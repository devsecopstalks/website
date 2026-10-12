import hashlib
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import botocore.exceptions

import r2_staging

PUBLIC = "https://media.example"


def client_error(code):
    return botocore.exceptions.ClientError({"Error": {"Code": code, "Message": code}}, "op")


def expiring(rule_id, **where):
    return {"ID": rule_id, "Status": "Enabled", "Expiration": {"Days": 7}, **where}


class CoverKeyTests(unittest.TestCase):
    def test_key_is_content_addressed(self):
        digest = hashlib.sha256(b"png").hexdigest()[:12]
        self.assertEqual(r2_staging.cover_r2_key(7, b"png"), f"covers/007-{digest}.png")
        self.assertNotEqual(r2_staging.cover_r2_key(7, b"png"), r2_staging.cover_r2_key(7, b"png2"))


class LifecycleTests(unittest.TestCase):
    def test_rules_that_could_expire_covers(self):
        rules = [
            expiring("whole-bucket", Filter={}),
            expiring("empty-prefix", Filter={"Prefix": ""}),
            expiring("parent", Filter={"Prefix": "cov"}),
            expiring("inside", Filter={"And": {"Prefix": "covers/old/", "Tags": []}}),
            expiring("legacy", Prefix=""),
            expiring("staging", Filter={"Prefix": "podcast/youtube-staging/"}),
            {"ID": "disabled", "Status": "Disabled", "Expiration": {"Days": 1}, "Filter": {}},
            {"ID": "abort-only", "Status": "Enabled", "Filter": {},
             "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1}},
        ]
        self.assertEqual(r2_staging.expiring_cover_rules(rules),
                         ["whole-bucket", "empty-prefix", "parent", "inside", "legacy"])

    def test_check_stops_on_matching_rule(self):
        s3 = mock.Mock()
        s3.get_bucket_lifecycle_configuration.return_value = {"Rules": [expiring("all", Filter={})]}
        with self.assertRaisesRegex(r2_staging.R2CoverError, "all"):
            r2_staging.check_cover_lifecycle(s3)

    def test_check_passes_without_lifecycle_or_with_unrelated_rule(self):
        s3 = mock.Mock()
        s3.get_bucket_lifecycle_configuration.side_effect = client_error("NoSuchLifecycleConfiguration")
        r2_staging.check_cover_lifecycle(s3)
        s3.get_bucket_lifecycle_configuration.side_effect = None
        s3.get_bucket_lifecycle_configuration.return_value = {
            "Rules": [expiring("staging", Filter={"Prefix": "podcast/youtube-staging/"})]}
        r2_staging.check_cover_lifecycle(s3)

    def test_check_stops_when_rules_cannot_be_read(self):
        s3 = mock.Mock()
        s3.get_bucket_lifecycle_configuration.side_effect = client_error("AccessDenied")
        with self.assertRaises(r2_staging.R2CoverError):
            r2_staging.check_cover_lifecycle(s3)

    def test_check_reads_the_covers_bucket(self):
        s3 = mock.Mock()
        s3.get_bucket_lifecycle_configuration.return_value = {"Rules": []}
        with mock.patch.object(r2_staging, "R2_COVERS_BUCKET", "covers-bucket"):
            r2_staging.check_cover_lifecycle(s3)
        s3.get_bucket_lifecycle_configuration.assert_called_once_with(Bucket="covers-bucket")


class CoverConfigTests(unittest.TestCase):
    def test_missing_covers_variables_are_named_without_staging_fallback(self):
        with mock.patch.object(r2_staging, "_r2_s3_client", return_value=object()), \
                mock.patch.object(r2_staging, "R2_BUCKET", "podcast-staging"), \
                mock.patch.object(r2_staging, "R2_PUBLIC_URL", PUBLIC):
            for bucket, url, missing in (("", PUBLIC, "R2_COVERS_BUCKET"),
                                         ("covers-bucket", "", "R2_COVERS_PUBLIC_URL")):
                with mock.patch.object(r2_staging, "R2_COVERS_BUCKET", bucket), \
                        mock.patch.object(r2_staging, "R2_COVERS_PUBLIC_URL", url):
                    with self.assertRaisesRegex(r2_staging.R2CoverError, missing):
                        r2_staging.require_cover_client()


@mock.patch.object(r2_staging, "R2_COVERS_BUCKET", "covers-bucket")
@mock.patch.object(r2_staging, "R2_COVERS_PUBLIC_URL", PUBLIC)
class UploadCoverTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.png = os.path.join(tmp.name, "cover.png")
        with open(self.png, "wb") as f:
            f.write(b"png")
        self.key = r2_staging.cover_r2_key(12, b"png")

    def test_public_url_known_before_upload(self):
        self.assertEqual(r2_staging.cover_public_url(self.png, 12), f"{PUBLIC}/{self.key}")

    def test_uploads_with_immutable_cache_header(self):
        s3 = mock.Mock()
        s3.head_object.side_effect = client_error("404")
        url = r2_staging.upload_cover_to_r2(self.png, 12, s3=s3)
        self.assertEqual(url, f"{PUBLIC}/{self.key}")
        s3.upload_file.assert_called_once_with(
            self.png, "covers-bucket", self.key,
            ExtraArgs={"ContentType": "image/png",
                       "CacheControl": "public, max-age=31536000, immutable"})

    def test_skips_upload_when_object_exists(self):
        s3 = mock.Mock()
        self.assertEqual(r2_staging.upload_cover_to_r2(self.png, 12, s3=s3), f"{PUBLIC}/{self.key}")
        s3.upload_file.assert_not_called()

    def test_upload_failure_raises(self):
        s3 = mock.Mock()
        s3.head_object.side_effect = client_error("404")
        s3.upload_file.side_effect = client_error("InternalError")
        with self.assertRaises(r2_staging.R2CoverError):
            r2_staging.upload_cover_to_r2(self.png, 12, s3=s3)

    def test_unconfigured_r2_raises(self):
        with mock.patch.object(r2_staging, "_r2_s3_client", return_value=None):
            with self.assertRaises(r2_staging.R2CoverError):
                r2_staging.upload_cover_to_r2(self.png, 12)
        with mock.patch.object(r2_staging, "R2_COVERS_PUBLIC_URL", ""):
            with self.assertRaises(r2_staging.R2CoverError):
                r2_staging.cover_public_url(self.png, 12)


if __name__ == "__main__":
    unittest.main()
