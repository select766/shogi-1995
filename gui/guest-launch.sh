#!/bin/bash
export DISPLAY=:0
export LD_LIBRARY_PATH=/lib:/usr/lib:/usr/X11R6/lib
export SHOGI_GUI_HOME=/usr/local/lib/shogi-gui
export SHOGI_GUI_CONFIG=/etc/shogi-gui.conf
# Debug mode is opt-in by creating this file from the serial diagnostic console.
if [ -f /tmp/shogi-gui-debug ]; then
    [ -p /tmp/shogi-gui.fifo ] || /bin/mkfifo /tmp/shogi-gui.fifo
    export SHOGI_GUI_DEBUG=/tmp/shogi-gui.fifo
fi
exec /usr/bin/wish -f /usr/local/lib/shogi-gui/app.tcl
