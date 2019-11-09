#!/usr/bin/env bash

# Script modified from this amazing gist:
# https://gist.github.com/Blaradox/030f06d165a82583ae817ee954438f2e

# TODO: Use .ini/.cfg file so that paths to icons aren't hard-coded

function get_volume {
  amixer get Master | grep '%' | head -n 1 | cut -d '[' -f 2 | cut -d '%' -f 1
}

function is_mute {
  amixer get Master | grep '%' | grep -oE '[^ ]+$' | grep off > /dev/null
}

function send_notification {
  iconSound=~/.config/dunst/icons/volume_light.png
  iconMuted=~/.config/dunst/icons/muted_grey.png

  # Make the bar with the special character ─ (it's not dash -)
  # https://en.wikipedia.org/wiki/Box-drawing_character
  volume=$(get_volume)
  bar=$(seq --separator="─" 0 "$((volume / 5))" | sed 's/[0-9]//g')

  if is_mute ; then
    dunstify -a volume -i $iconMuted -r 2593 -u low "    $bar"
  else
    dunstify -a volume -i $iconSound -r 2593 -u normal "    $bar"
  fi
}

case $1 in
  up)
    # set the volume on (if it was muted)
    pactl set-sink-mute 0 0
    # up the volume (+ 5%)
    pactl set-sink-volume 0 +10%
    send_notification
    ;;
  down)
    pactl set-sink-volume 0 -10%
    send_notification
    ;;
  mute)
    # toggle mute
    pactl set-sink-mute 0 toggle
    send_notification
    ;;
esac
