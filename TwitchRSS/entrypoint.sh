#!/bin/bash

gunicorn -b ${HOST}:${PORT:-8000} -k gthread --threads 3 twitchrss:app