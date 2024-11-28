#!/bin/bash
#pipe in
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT

ffmpeg -y $1 -ar 44100 -ac 2 -f wav $2 2>/dev/null & 
#cat $1 > $2 &
echo "Connecting..."
socat STDIO OPENSSL-CONNECT:mana.kyun.li:14880 < $2 > $3


