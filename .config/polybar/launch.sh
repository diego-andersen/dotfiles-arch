#!/usr/bin/env bash

# This is used by ~/.config/rofi/scripts/rofi_conky to bring conky to the front
WINDOW_ID_CONKY=/tmp/conky_window_id

launch_conky() {
    # Hacky X11 magic to make Conky appear above polybar
    killall conky

    # xdotool search can't find Conky's window but fortunately Conky outputs it
    conky 2> /tmp/conky_out

    # Extract the hex window id from Conky's output
    HEX=$(awk '/drawing to created window/ {print $NF}' /tmp/conky_out | tr -d '()' | awk -Fx '{print $2}')
    WIN_ID=$(( 16#$HEX )) # convert to decimal
    xdotool windowunmap $WIN_ID
    echo $WIN_ID > $WINDOW_ID_CONKY
}

(
    flock 200

    # Terminate already running bar instances
    killall -q polybar
    while pgrep -u $UID -x polybar > /dev/null; do sleep 0.5; done

    launch_conky

    OUTPUTS=$(polybar -m | cut -d ":" -f1)

    # Polybar thinks the external is the only monitor when mirroring displays 
    if [[ $(echo $OUTPUTS | wc -l) == 1 ]]; then
        TRAY_OUTPUT=$OUTPUTS
    else
        TRAY_OUTPUT=eDP1
    fi

    for m in $OUTPUTS; do
        export MONITOR=$m
        export TRAY_POSITION=none

        if [[ $m == $TRAY_OUTPUT ]]; then
            TRAY_POSITION=right
        fi

        polybar -c ~/.config/polybar/config.ini -r bottom </dev/null >/var/tmp/polybar-$m.log 2>&1 200>&- &
        disown

    done

) 200>/var/tmp/polybar-launch.lock
