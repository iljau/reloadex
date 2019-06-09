#!/usr/bin/env bash
uwsgi --http :9090 --enable-threads --master --workers 2 --wsgi-file app_flask.py