rm audio_in
rm audio_out
mkfifo audio_in
mkfifo audio_out
ffmpeg -y -f pulse -sample_rate 44100 -channels 1 -i hw:0 -f flac audio_in &
cat audio_in | openssl s_client -connect mana.kyun.li 14880 | audio_out &
mpv audio_out

