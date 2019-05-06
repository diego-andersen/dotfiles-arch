#!/usr/bin/env bash

source ~/scripts/rofi/rofi_dmenu.sh

exec 2>&1 > /dev/null

if [[ $(pgrep "rofi") ]]; then
        exit 1
fi

rofi_load_vars power

rofi_dmenu &

rofi_window_show

rofi_dmenu_read

case $choice in
    1) # Lock the screen
        light-locker-command -l
        ;;
    2) # Logout
        i3-msg exit
        ;;
    3) # Reboot
        systemctl reboot
        ;;
    4) # Shut down
        systemctl poweroff -i
        ;;
esac

