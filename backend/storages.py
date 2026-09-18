"""Cloudflare R2 storage backends (S3-compatible).

Two buckets are used:

* the public one holds product/brand photos, which are served straight from
  R2's public URL so image requests never reach gunicorn;
* the private one holds customer bill uploads, which are only reachable
  through short-lived signed URLs.

These classes are only imported when the R2_* environment variables are set
(see ``STORAGES`` in settings), so local development keeps using the plain
filesystem storage under MEDIA_ROOT.
"""

import os

from django.core.files.storage import FileSystemStorage
from storages.backends.s3 import S3Storage


class _R2Storage(S3Storage):
    """Shared connection settings for both buckets."""

    endpoint_url = os.environ.get('R2_ENDPOINT')
    access_key = os.environ.get('R2_ACCESS_KEY_ID')
    secret_key = os.environ.get('R2_SECRET_ACCESS_KEY')
    region_name = 'auto'
    signature_version = 's3v4'

    # R2 exposes buckets at <endpoint>/<bucket>/<key>, not as subdomains.
    addressing_style = 'path'

    # R2 has no ACL support - visibility is a per-bucket setting instead.
    default_acl = None

    # Never silently replace an existing object; Django adds a random suffix
    # when a name collides, exactly like FileSystemStorage does.
    file_overwrite = False


class PublicMediaStorage(_R2Storage):
    """Product and brand photos, served from the public R2 URL."""

    bucket_name = os.environ.get('R2_BUCKET')
    custom_domain = os.environ.get('R2_PUBLIC_URL')
    querystring_auth = False


class PrivateMediaStorage(_R2Storage):
    """Customer bill uploads - signed URLs only, never public."""

    bucket_name = os.environ.get('R2_PRIVATE_BUCKET')
    custom_domain = None
    querystring_auth = True
    querystring_expire = 3600  # one hour is plenty for an admin click-through


def private_media_storage():
    """Storage for bill uploads, resolved at field-definition time.

    Passing a callable (rather than a storage instance) to ``FileField`` keeps
    the choice out of migrations, so the backend can change without touching
    the database.
    """
    if os.environ.get('R2_PRIVATE_BUCKET'):
        return PrivateMediaStorage()
    return FileSystemStorage()
