buffer_size = 1024 * 4

fifo_pipes_root = "/tmp/memevoip/"
server_sleep_time = 3
#ffmpeg_client_in = "-i /home/mana/Music/meme.opus".split(" ")
ffmpeg_client_in = "-f pulse -i hw:2".split(" ")playback_command = "aplay -f cd".split(" ")playback_command = "aplay -f cd".split(" ")