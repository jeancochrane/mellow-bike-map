#!/bin/sh
set -e

if [ "$DJANGO_MANAGEPY_MIGRATE" = 'on' ]; then
    python manage.py migrate --noinput
fi

if [ "$DJANGO_ENV" = 'prod' ]; then
    nginx -c /app/app/nginx.conf &
    exec gunicorn mbm.wsgi:application \
        --bind 127.0.0.1:8000 \
        --workers 2 \
        --threads 4 \
        --timeout 60 \
        --access-logfile - \
        --error-logfile - \
        --log-level info
else
    exec python manage.py runserver 0.0.0.0:8000
fi
