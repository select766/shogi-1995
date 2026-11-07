#!/bin/bash
export PATH=/bin:/sbin:/usr/bin:/usr/X11R6/bin:/usr/local/bin
export LD_LIBRARY_PATH=/lib:/usr/lib:/usr/X11R6/lib
export HOME=/root
export DISPLAY=:0
/usr/local/bin/gui-tools mount-proc
/usr/X11R6/bin/XF86_SVGA :0 -ac >/tmp/xserver.log 2>&1 &
sleep 4
/usr/X11R6/bin/twm >/tmp/twm.log 2>&1 &
/usr/X11R6/bin/xsetroot -solid '#547478'
# Serial shell is available only inside this VM for reproducible GUI diagnostics.
/usr/local/bin/shogi-gui >/tmp/shogi-gui-launch.log 2>&1 &
echo $! >/tmp/shogi-gui.pid
export PS1='gui1995# '
exec /bin/bash -i
