rm audio_in
rm audio_out
mkfifo audio_in
mkfifo audio_out
mpv audio_out
bash $(dirname "$0")/shell_client_internal.sh $1 audio_in audio_out &
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT
