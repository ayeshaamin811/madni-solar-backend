"""One-off copy of everything under MEDIA_ROOT into Cloudflare R2.

Covers media from every app, not just products - it lives here only because
management commands have to belong to an installed app.

The keys written to R2 are the paths already stored in the database (e.g.
"batteries/products/panel.jpg"), so no rows need updating: once the storage
backend is switched, the existing values resolve to the uploaded objects.

Files are only read from disk; nothing on the volume is written or deleted.
Safe to run repeatedly - objects already in the bucket are skipped unless
--overwrite is given.
"""

from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

# Bills are customer documents and belong in the private bucket; everything
# else is a catalogue image served publicly.
PRIVATE_PREFIX = 'calculator/bills/'


class Command(BaseCommand):
    help = 'Upload every file under MEDIA_ROOT to the configured R2 buckets.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List what would be uploaded without touching R2.',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Re-upload files that already exist in the bucket.',
        )

    def handle(self, *args, **options):
        from backend.storages import PrivateMediaStorage, PublicMediaStorage

        if not settings.USE_R2:
            raise CommandError('R2 is not configured - set the R2_* environment variables first.')

        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.is_dir():
            self.stdout.write(f'Nothing to do: {media_root} does not exist.')
            return

        dry_run = options['dry_run']
        overwrite = options['overwrite']

        # file_overwrite lets save() write the exact key instead of appending a
        # random suffix, which would break the paths already in the database.
        public = PublicMediaStorage(file_overwrite=True)
        private = PrivateMediaStorage(file_overwrite=True)

        uploaded = skipped = failed = 0
        uploaded_bytes = 0

        for path in sorted(media_root.rglob('*')):
            if not path.is_file():
                continue

            key = path.relative_to(media_root).as_posix()
            storage = private if key.startswith(PRIVATE_PREFIX) else public
            label = 'private' if storage is private else 'public'

            if not overwrite and storage.exists(key):
                skipped += 1
                self.stdout.write(f'  skip    {key}')
                continue

            if dry_run:
                uploaded += 1
                self.stdout.write(f'  would   {key} -> {label}')
                continue

            try:
                with path.open('rb') as handle:
                    storage.save(key, File(handle))
            except Exception as exc:  # keep going; report the total at the end
                failed += 1
                self.stderr.write(f'  FAILED  {key}: {exc}')
                continue

            uploaded += 1
            uploaded_bytes += path.stat().st_size
            self.stdout.write(f'  upload  {key} -> {label}')

        summary = (
            f'{uploaded} uploaded ({uploaded_bytes / 1_048_576:.1f} MB), '
            f'{skipped} already present, {failed} failed'
        )
        if failed:
            self.stderr.write(self.style.ERROR(summary))
            raise CommandError('Some files could not be uploaded.')
        self.stdout.write(self.style.SUCCESS(summary))
