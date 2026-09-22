#! /usr/bin/env bash

set -e
set -x

# Run migrations
alembic upgrade head

# Create initial data in DB.
# PYTHONSAFEPATH keeps app/email.py from shadowing the stdlib email package.
PYTHONSAFEPATH=1 python app/initial_data.py
