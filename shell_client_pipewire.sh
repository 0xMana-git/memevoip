rm audio_in
rm audio_out
rm audio_pw.wav
mkfifo audio_pw.wav
mkfifo audio_in
mkfifo audio_out
pw-record --rate 44100 pwrec.out --target $1 &
sleep 0.1
tail -f -n +1 pwrec.out > audio_pw.wav &
bash $(dirname "$0")/shell_client_internal.sh "-f wav -i audio_pw.wav" audio_in audio_out &
mpv audio_out
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT
