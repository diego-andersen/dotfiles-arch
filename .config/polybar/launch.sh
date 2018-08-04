#!/usr/bin/env sh

# Terminate already running bar instances
killall -q polybar

# Launch whatever bars
polybar -r bottom
