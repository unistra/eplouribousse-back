#! /usr/bin/env sh
set -e
echo "Running inside /app/docker-prestart.sh"

cd /app
python manage.py migrate --noinput

exec "$@"
