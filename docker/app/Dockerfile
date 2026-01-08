FROM python:3.12-slim AS builder

RUN mkdir /app

WORKDIR /app


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN set -ex \
    && apt update \
    && apt install -y build-essential xmlsec1 gcc gettext libpq-dev locales tzdata \
    && localedef -i fr_FR -c -f UTF-8 -A /usr/share/locale/locale.alias fr_FR.UTF-8 \
    && ln -fs /usr/share/zoneinfo/Europe/Paris /etc/localtime \
    && dpkg-reconfigure --frontend noninteractive tzdata \
    && apt clean && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY ./requirements/prod.txt /app/requirements.txt
RUN pip install --no-cache -r requirements.txt

FROM python:3.12-slim

ARG SECRET_KEY="django-insecure-temporary-for-build-only"

# Needed for weasyprint
RUN apt update && apt install -y --no-install-recommends \
    gettext libglib2.0-0 libgobject-2.0-0 libpango-1.0-0 libpangoft2-1.0-0 \
    && apt clean && rm -rf /var/lib/apt/lists/*

RUN useradd -m -r appuser && \
    mkdir /app && \
    chown -R appuser /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy xmlsec1 and its dependencies
COPY --from=builder /usr/bin/xmlsec1 /usr/bin/xmlsec1
RUN ldd /usr/bin/xmlsec1 2>/dev/null | grep "=> /" | awk '{print $3}' \
    | xargs -I '{}' sh -c 'mkdir -p $(dirname {}) && cp {} {}' 2>/dev/null || true

WORKDIR /app

COPY --chown=appuser:appuser . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SECRET_KEY=${SECRET_KEY}
ENV DJANGO_SETTINGS_MODULE=epl.settings.docker

#USER appuser
EXPOSE 8080

RUN python manage.py collectstatic --settings=epl.settings.docker --noinput && \
    python manage.py compilemessages --settings=epl.settings.docker

RUN chgrp -R 0 /app && \
    chmod -R g+rwX /app

ENTRYPOINT ["sh", "/app/docker-prestart.sh"]

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-", "epl.wsgi:application"]
