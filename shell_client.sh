rm audio_in
rm audio_out
mkfifo audio_in
mkfifo audio_out

trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT

args="${@:1}"
bash $(dirname "$0")/shell_client_internal.sh "$args" audio_in audio_out &
mpv audio_out

