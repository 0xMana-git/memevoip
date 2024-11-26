rm dummy_in
mkfifo dummy_in
bash $(dirname "$0")/shell_client_internal.sh /home/mana/Music/meme.opus dummy_in /dev/null &
sleep infinity
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT
