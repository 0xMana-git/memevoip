#pipe in
ffmpeg -y  -i $1 -ar 44100 -ac 2 -f wav $2 2>/dev/null &
#pipe ncat
socat STDIO OPENSSL-CONNECT:mana.kyun.li:14880 < $2 > $3

trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT
