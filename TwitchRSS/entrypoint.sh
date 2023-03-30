#!/bin/bash

gunicorn -k gthread --threads 3 twitchrss:app