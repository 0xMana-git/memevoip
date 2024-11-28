python server.py
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT
