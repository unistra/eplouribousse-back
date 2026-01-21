# Documentation technique – eplouribousse

Ce document décrit l’installation locale et la mise en production de l’application eplouribousse (backend Django
multi‑tenant + frontend Vue/Quasar).

## Architecture

- Backend Django [multi‑tenant](https://django-tenants.readthedocs.io/en/latest/) exposant les APIs sous `/api/` et la documentation sous
  `/api/docs/`.
- Frontend [Vue.js](https://vuejs.org/) + [Vite](https://vite.dev/) + [Quasar](https://quasar.dev/) ; le domaine front est mappé vers le domaine back via un sous-domaine `-api` (
  voir src/plugins/axios/axiosUtils.ts
- Santé : endpoint `/healthz/` servi avant la résolution de tenant epl/middleware.py. Sa fonction
  est de vérifier la disponibilité minimale de l’application.

## Prérequis système

- Python 3.12
- Poetry
- PostgreSQL (schémas par tenant via django-tenants). Version recommandée : 14 ou supérieure.
- Redis pour la mise en cache des calculs du dashboard. Si on ne dispose pas de Redis, Django il faut configurer 
un backend de cache alternatif dans les settings.

## Backend (Django, dossier `epl/`)

### Variables d’environnement clés

| Variable                 | Usage                                                       |
|--------------------------|-------------------------------------------------------------|
| `DJANGO_SETTINGS_MODULE` | Choix du profil (`epl.settings.dev`, `epl.settings.docker`) |
| `DATABASE_HOST`          | Hôte Postgres                                               |
| `DATABASE_USER`          | Nom d'utilisateur Postgres                                  |
| `DATABASE_PASSWORD`      | Mot de passe Postgres                                       |
| `DATABASE_NAME`          | Nom de la base Postgres                                     |
| `SECRET_KEY`             | Secret Django                                               |
| `JWT_PRIVATE_KEY`        | Clés RSA privée pour JWT                                    |
| `JWT_PUBLIC_KEY`         | Clés RSA privée pour JWT                                    |
| `REDIS_HOST`             | Hôte du serveur Redis                                       |  
| `REDIS_PORT`             | Port du serveur Redis                                       |
| `REDIS_DB`               | Numéro de la base Redis                                     |
| `CACHE_VERSION`          | Nom de la version du cache                                  |
| `EMAIL_HOST`             | Hôte SMTP                                                   |
| `EMAIL_PORT`             | Port SMTP                                                   |
| `EMAIL_HOST_USER`        | Nom d'utilisateur SMTP                                      |
| `EMAIL_HOST_PASSWORD`    | Mot de passe SMTP                                           |
| `EMAIL_USE_TLS`          | Utilisation de TLS                                          |
| `LOG_LEVEL`              | Niveau de log                                               |
| `LOG_DIR`                | Répertoire des fichiers de log                              |


Autres points de configuration :

SAML : clés privée et publique attendues dans `keys/saml2-private.key` et `keys/saml2-public.pem`, plus le bloc `SAML_CONFIG`/
  `SAML_TENANT_CONFIG`

Générer les clés JWT (RSA RS256) locales :

```bash
mkdir -p keys
ssh-keygen -t rsa -b 4096 -m PEM -f keys/jwtRS256.key
openssl rsa -in keys/jwtRS256.key -pubout -outform PEM -out keys/jwtRS256.key.pub
```

### Déploiement local (environnement de developpement)

Installer les dépendances du Projet :

```bash
poetry env use python3.12
poetry install
```

#### Démarrer l’infra locale (Postgres, Redis, Maildev) :

```
docker compose -f docker-compose.dev.yaml up -d
```

#### Préparer le fichier `.env` à la racine du projet :

- `DJANGO_SETTINGS_MODULE="epl.settings.dev"`

Compléter avec les variables d'environnement nécessaires (voir tableau plus haut).

#### Faire les migrations :

```
python manage.py migrate
```

#### Lancer le conteneur Django pour l'infrastructure (Postgres, Redis, Maildev) :

```
python manage.py runserver
```

#### Créer un tenant :

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
python manage.py delete_tenant
```
#### Créer un super-utilisateur de tenant :

```aiignore
python manage.py create_tenant_superuser --schema sxb

```

Dans le cas des comptes locaux, il est important de réutiliser l'adresse email comme nom d'utilisateur.

Doc django-tenants : https://django-tenants.readthedocs.io/en/latest/

#### Vérifications rapides (port 8080) :

- `http://localhost:8080/healthz/` → `ok`
- Accès à la documentation de l'API : `http://sxb.epl-api.localhost:8080/api/docs/`

Vérifier que l'application délivre des tokens JWT via l'endpoint `/api/token/` :

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"email": "user@eplouribousse.fr", "password": "boatymcboatface"}' \
  http://sxb.epl-api.localhost:8080/api/token/
```

#### Front en local

- Installer les dépendances : `pnpm install`
- Démarrer le front : `pnpm dev`
- ouvrir `http://sxb.epl.localhost:5173`
 
Le front appellera automatiquement le back `sxb.epl-api.localhost:8080` grâce à la réécriture 
de domaine dans `src/plugins/axios/axiosUtils.ts`.


## Outils

Le projet est configuré pour utiliser plusieurs outils facilitant le développement et la maintenance.

### Sentry

[Sentry](https://sentry.io/) est utilisé pour la supervision des erreurs en production et préproduction. Il est activé si la variable
d’environnement `SENTRY_DSN` est définie.

### SonarQube

[SonarQube](https://www.sonarqube.org/) est utilisé pour l’analyse statique du code. Un scanner Sonar est
configuré dans le fichier `sonar-project.properties` à la racine du projet.
