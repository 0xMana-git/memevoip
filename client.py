import ssl
import os
import threading
import socket
import logging
import signal
import subprocess
import sys
import utils

logger = logging.getLogger(__name__)
fifo_in_path = "audio_in"
fifo_out_path = "audio_out"

sock_raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock_raw.settimeout(10)

HOST, PORT = "mana.kyun.li", 14880
pipe_paths = "pipes/"
key_base = "/etc/letsencrypt/live/mana.kyun.li"
keyfile = key_base + "/privkey.pem"
certfile = key_base + "/fullchain.pem"
#4kb
buffer_size = 1024 * 4
muxout_path = "muxed_out"
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
sock = context.wrap_socket(sock_raw)
sock_open = True

def mkfifo(fpath, open_mode, do_open=True):
    os.mkfifo(fpath, 0o600)
    fmode = "rb"
    if(open_mode == os.O_WRONLY):
        fmode = "wb"
    if do_open:
        return os.fdopen(os.open(fpath, os.O_NONBLOCK | open_mode), fmode)

def send_thread(fifo):
    global sock_open
    while sock_open:
        buffer_send = fifo.read(buffer_size)
        sock.send(buffer_send)
        #print("sent bufsize")

process_handle_playback = None
process_handle_record = None
def recv_thread(fifo):
    global sock_open
    while sock_open:
        buffer_recv = sock.recv(buffer_size)
        if not buffer_recv:
            sock_open = False
            print("EOF reached")
            return
        fifo.write(buffer_recv)
        #print("recv bufsize")

def main():
    global process_handle_playback
    global process_handle_record
    utils.remove_silent(fifo_in_path)
    utils.remove_silent(fifo_out_path)
    os.mkfifo(fifo_in_path)
    os.mkfifo(fifo_out_path)
    print("Initializing playback stream...")
    process_handle_playback = subprocess.Popen(["aplay", "-f", "cd", "audio_out"])
    fifo_out = os.fdopen(os.open(fifo_out_path, os.O_WRONLY|os.O_NONBLOCK))
    
    print("Initializing input stream...")
    fifo_in = os.fdopen(os.open(fifo_in_path, os.O_RDONLY|os.O_NONBLOCK))
    process_handle_record = subprocess.Popen(["ffmpeg", "-y", "-f", "pulse", "-sample_rate", "44100", "-channels", "2", "-i", "hw:0", "-f", "wav", "audio_in"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL)
    print("Connecting to host")
    sock.connect((HOST, PORT))
    print("Connected")
    sock_open = True
    
    st = threading.Thread(target=send_thread, args=(fifo_in,))
    rt = threading.Thread(target=recv_thread, args=(fifo_out,))
    st.start()
    rt.start()
    st.join()
    rt.join()


def handle_int(sig, frame):
    sock.close()
    sock_open = False
    if process_handle_record != None:
        process_handle_record.kill()
    if process_handle_playback != None:
        process_handle_playback.kill()
    print("Exiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_int)

if __name__ == "__main__":
    main()
