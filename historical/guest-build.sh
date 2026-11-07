#!/bin/bash
set -e
cd /work/old/src
rm -f *.o gnushogir
gcc -v
make -j1 gnushogir CFLAGS='-O2 -funroll-loops -m486' LIBDIR=/work/old/misc > /work/build-old.log 2>&1
echo OLD_BUILD_EXIT=$?
while read line; do echo "$line"; done < /work/build-old.log
cd /work/modern
gcc -o gnushogir mainN.o globals.o bookN.o genmoveR.o patternR.o ataksR.o utilR.o evalR.o initR.o searchR.o tcontrlN.o dspcomR.o nondspR.o -lm > /work/link-modern.log 2>&1
echo MODERN_LINK_EXIT=$?
gcc -O2 -m486 -o /work/relay /work/relay.c
echo RELAY_BUILD_EXIT=$?
echo 'main(){sync();sleep(2);sync();return mount("","/","ext2",0xc0ed0021,0);}' > /work/sync.c
gcc -o /work/sync /work/sync.c
/work/sync
echo SYNC_EXIT=$?
echo BUILD_FINISHED
