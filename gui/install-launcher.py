#!/usr/bin/env python3
"""Install the desktop entry for the current checkout, without changing the engine checkout."""
import argparse
import os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--deps',type=Path,required=True);p.add_argument('--directory',type=Path)
a=p.parse_args();root=Path(__file__).resolve().parent.parent
folder=a.directory or Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'applications'
folder.mkdir(parents=True,exist_ok=True)
def quote(s):
    return '"'+str(s).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'
entry=folder/'shogi-1995-guest.desktop'
entry.write_text('[Desktop Entry]\nType=Application\nName=Shogi 1995 (Guest)\nName[ja]=将棋 1995（ゲスト）\nComment=Play shogi inside the Slackware 3.0 guest\nExec=/usr/bin/python3 '+quote(root/'gui/run-guest.py')+' --deps '+quote(a.deps.resolve())+'\nIcon=applications-games\nTerminal=false\nCategories=Game;BoardGame;\nStartupNotify=false\n')
entry.chmod(0o755);print(entry)
