# Polynym - Contextual Identity and Profile Management API

Polynym is a Django REST Framework API that stores multiple identities for the same person:
legal, preferred, chosen, religious, professional and username.

Authenticated callers are assigned roles such as Self, HR, Public or Medical. The API uses role-based
policies to decide which identity records each caller may read or write. This means the same person can be represented in different contexts while limiting disclosure of personal information.

GDPR data minimisation principles and privacy played an important role in shaping the design.

CM3070 Computer Science Final Project, University of London.
Based on Project Template 7.1: Identity and Profile Management API.

## Tech stack

- Python
- Django
- Django REST Framework
- SQLite
- JWT authentication using djangorestframework-simplejwt
- drf-spectacular for OpenAPI documentation

## Setup

Create and activate a virtual environment:

    python3 -m venv venv
    source venv/bin/activate

Install the runtime dependencies:

    pip install -r requirements.txt

Set the Django secret key:

    export DJANGO_SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"

For local development:

    export DJANGO_DEBUG=True

Set passwords for the four demonstration accounts:

    export DEMO_SELF_PASSWORD="choose-a-password"
    export DEMO_HR_PASSWORD="choose-a-password"
    export DEMO_PUBLIC_PASSWORD="choose-a-password"
    export DEMO_MEDICAL_PASSWORD="choose-a-password"

Apply the database migrations and create the demonstration data:

    python manage.py migrate
    python manage.py seed_demo

If running Django inside Ubuntu on WSL, find the current WSL IP address:

    hostname -I

Add the current WSL IP address to the allowed hosts, for example:

    export DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost,172.22.79.59"

Start the development server:

    python manage.py runserver 0.0.0.0:8000

When running Django inside Ubuntu on WSL, open the demonstration frontend
in the Windows browser using:

    http://<WSL-IP>:8000/demo/

For example:

    http://172.22.79.59:8000/demo/

The Swagger UI for the OpenAPI documentation is available at:

    http://<WSL-IP>:8000/api/docs/

## Running tests

Run the complete application test suite:

    python manage.py test identity

The current test suite contains 63 tests covering authentication,
authorisation, contextual disclosure, write permissions, erasure,
audit logging and language-aware identity selection.

## Development checks

Install the development dependencies:

    pip install -r requirements-dev.txt

Run Ruff:

    ruff check .

Run test coverage:

    coverage erase
    coverage run manage.py test identity
    coverage report -m

Validate the OpenAPI schema:

    python manage.py spectacular --file /tmp/polynym-schema.yml --validate
