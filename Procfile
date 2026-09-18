# TEMPORARY: migrate_media_to_r2 copies the files still sitting on the Railway
# volume into R2. It only reads from the volume, skips objects already in the
# bucket, and `|| true` keeps a failure from blocking startup. Drop that call
# once the upload has run successfully.
web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && (python manage.py migrate_media_to_r2 || true) && gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT
