#pipe in
ffmpeg -y $1 -ar 44100 -ac 2 -f wav $2 2>/dev/null &
#pw-record --rate 44100 --target 145 $2 &
#pipe ncat
echo "Connecting..."
socat STDIO OPENSSL-CONNECT:mana.kyun.li:14880 < $2 > $3

trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT
