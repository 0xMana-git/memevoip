python server.py &
sleep infinity
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT
