rm dummy_in
mkfifo dummy_in

trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT

args="${@:1}"
bash $(dirname "$0")/shell_client_internal.sh "$args" dummy_in /dev/null 
