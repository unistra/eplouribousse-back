tag := "develop"
env := "test"

@default:
    just --list

# 🚀 start all the docker
up:
    @docker compose up -d

# 🛑 stop docker
down:
    @docker compose down

# 🦄 start the Django server
serve:
    @poetry run python manage.py runserver

# ✅ run the tests
test *ARGS:
    poetry run coverage run --source . run_tests.py {{ARGS}}
    poetry run coverage report

# ☁️ deploy
deploy tag env:
    echo "fab tag:{{ tag }} {{ env }} deploy -u root"
