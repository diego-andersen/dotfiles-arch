#!/bin/sh
grep "\w" | grep -v "^#" | sed "s/#\ .*//" | perl -lane "printf '%s=%s:', shift @F, join ';', @F;"
