rm audio_in
rm audio_out
mkfifo audio_in
mkfifo audio_out
bash $(dirname "$0")/shell_client_internal.sh /home/mana/Music/meme.opus audio_in audio_out &
aplay -f cd audio_out
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT
