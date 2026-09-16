# Polynym - Contextual Identity and Profile Management API

A Django REST Framework API that stores multiple named identities per person
(legal, preferred, chosen, religious, username). It returns only the identity
fields a caller's role permits and enforcing GDPR data minimisation at query time.

CM3070 Computer Science Final Project, University of London.
Based on Project Template 7.1: Identity and Profile Management API.

## Tech stack

Django + Django REST Framework
SQLite3
JWT authentication (djangorestframework-simplejwt)

## Setup

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python manage.py migrate
    python manage.py seed_demo
    python manage.py runserver

## Running tests

    python manage.py test
