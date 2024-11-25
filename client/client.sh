rm audio_in
rm audio_out
mkfifo audio_in
mkfifo audio_out
#should be IN THIS EXACT ORDER
#mpv audio_out &
python client.py &
ffmpeg -y -f pulse -sample_rate 44100 -channels 1 -i hw:0 -f wav audio_in 2>/dev/null &


