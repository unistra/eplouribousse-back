# Documentation technique – eplouribousse

Ce document décrit l’installation locale et la mise en production de l’application eplouribousse (backend Django
multi‑tenant + frontend Vue/Quasar).

## Architecture

- Backend Django multi‑tenant (django-tenants) exposant les APIs sous `/api/` et la documentation sous
  `/api/docs/` (epl/urls.py).
- Frontend Vue 3 + Vite + Quasar ; le domaine front est mappé vers le domaine back via un sous-domaine `-api` (
  voir src/plugins/axios/axiosUtils.ts
- Supervision : Sentry activé dans tous les
  environnements (epl/settings/base.py, epl/settings/prod.py, epl/settings/preprod.py)
- Santé : endpoint `/healthz/` servi avant la résolution de tenant epl/middleware.py. Sa fonction
  est de vérifier la disponibilité minimale de l’application.

## Prérequis système

- Python 3
- PostgreSQL (schémas par tenant via django-tenants)
- Redis pour la mise en cache des calculs du dashboard.

## Backend (Django, dossier `epl/`)

### Variables d’environnement clés

| Variable                                                                              | Usage                                                                                                    |
|---------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| `DJANGO_SETTINGS_MODULE`                                                              | Choix du profil (`epl.settings.dev`, `epl.settings.prod`, `epl.settings.preprod`, `epl.settings.docker`) |
| `DATABASE_HOST` / `USER` / `PASSWORD` / `NAME` / `PORT`                               | Connexion Postgres                                                                                       |
| `SECRET_KEY`                                                                          | Secret Django                                                                                            |
| `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`                                                   | Clés RSA pour JWT                                                                                        |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` / `CACHE_VERSION`                            | Cache des calculs du dashboard                                                                           |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | SMTP                                                                                                     |
| `LOG_LEVEL`, `LOG_DIR`                                                                | Logs                                                                                                     |
| `CSRF_TRUSTED_ORIGINS`                                                                | CSRF                                                                                                     |

Autres points de configuration :

- SAML : clés attendues dans `keys/saml2-private.key` et `keys/saml2-public.pem`, plus le bloc `SAML_CONFIG`/
  `SAML_TENANT_CONFIG`
- CAS : URL différente selon l’environnement (dev/prod/preprod/test) dans les fichiers de settings correspondants.

### Déploiement local

1) Démarrer l’infra locale (Postgres, Redis, Maildev) :

```
docker compose -f docker-compose.dev.yaml up -d
```

2) Générer les clés JWT locales :

```
mkdir -p keys
ssh-keygen -t rsa -b 4096 -m PEM -f keys/jwtRS256.key
openssl rsa -in keys/jwtRS256.key -pubout -outform PEM -out keys/jwtRS256.key.pub
```

3) Préparer le fichier `.env` à la racine du projet :

- `DJANGO_SETTINGS_MODULE="epl.settings.dev"`

4) Lancer le conteneur Django pour l'infrastructure (Postgres, Redis, Maildev) :

```
docker compose up -d
```

5) Faire les migrations :

```
python manage.py migrate
```

6) Créer un tenant et un super-utilisateur :

```
python manage.py create_tenant
```

Example avec un tenant `sxb` :

```
schema: sxb
name : Strasbourg
settings : (laisser vide pour le moment)
domain : sxb.epl-api.localhost
is primary : True
Frontend domain : sxb.epl.localhost
```

Note: pour supprimer un tenant :

```
docker compose exec app python manage.py delete_tenant
```

Doc django-tenants : https://django-tenants.readthedocs.io/en/latest/

7) Vérifications rapides (port 8080) :

- `http://sxb.epl-api.localhost:8080/healthz/` → `ok`
- Swagger : `http://sxb.epl-api.localhost:8080/api/docs/`
- JWT :

```
curl -X POST -H "Content-Type: application/json" \
  -d '{"email": "user@eplouribousse.fr", "password": "boatymcboatface"}' \
  http://sxb.epl-api.localhost:8080/api/token/
```

8) Front en local (via `pnpm dev`) : ouvrir `http://sxb.epl.localhost:5173`, le front appellera automatiquement le back
   `sxb.epl-api.localhost:8080` grâce à la réécriture de domaine dans axiosUtils.ts.
