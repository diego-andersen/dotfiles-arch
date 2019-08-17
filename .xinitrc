# start some nice programs
if [ -d /etc/X11/xinit/xinitrc.d ] ; then
 for f in /etc/X11/xinit/xinitrc.d/?*.sh ; do
  [ x- "$f" ] && . "$f"
 done
 unset f
fi

# keyboard mapping
setxkbmap gb

# start window manager
exec i3
