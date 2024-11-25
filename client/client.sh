rm audio_in
rm audio_out
mkfifo audio_in
mkfifo audio_out
ffmpeg -y -f pulse -sample_rate 44100 -channels 1 -i hw:0 -f wav audio_in &
python client.py &
mpv audio_out

