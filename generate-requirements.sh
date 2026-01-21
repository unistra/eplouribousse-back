#!/bin/bash

echo "📦️ generating common.txt"
poetry export -o requirements/common.txt --without-hashes

echo "📦️ generating prod.txt"
poetry export -o requirements/prod.txt --with prod

echo "📦️ generating dev.txt"
poetry export -o requirements/dev.txt --without-hashes --with dev
