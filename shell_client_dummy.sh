rm dummy_in
mkfifo dummy_in
args="${@:1}"
bash $(dirname "$0")/shell_client_internal.sh "$args" dummy_in 2>/dev/null &
sleep infinity
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT
