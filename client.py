import ssl
import os
import threading
import socket
import logging
import signal
import subprocess
import sys
import utils
import time
import cfg
import shutil

logger = logging.getLogger(__name__)

pipes_path = cfg.fifo_pipes_root + "client_pipes/"
fifo_in_path = pipes_path + "audio_in"
fifo_out_path = pipes_path + "audio_out"



HOST, PORT = "mana.kyun.li", 14880
pipe_paths = "pipes/"


muxout_path = "muxed_out"

g_do_exit = False
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
sock_raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock = context.wrap_socket(sock_raw)
sock_open = False
fifo_in = None
fifo_out = None

def send_thread(fifo):
    global sock_open
    while sock_open:
        buffer_send = fifo.read(cfg.buffer_size)
        sock.send(buffer_send)
        #print("sent bufsize")

process_handle_playback = None
process_handle_record = None
def recv_thread(fifo):
    global sock_open
    while sock_open:
        buffer_recv = sock.recv(cfg.buffer_size)
        if not buffer_recv:
            sock_open = False
            print("EOF reached")
            return
        fifo.write(buffer_recv)
        #print("recv bufsize")


    
def main():
    global process_handle_playback
    global process_handle_record
    global fifo_in
    global fifo_out
    global sock_open
    global sock
    global sock_raw
    sock_raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock = context.wrap_socket(sock_raw)
    sock_open = False
    fifo_in = None
    fifo_out = None

    shutil.rmtree(pipes_path, ignore_errors=True)
    os.makedirs(pipes_path, exist_ok=True)
    os.mkfifo(fifo_in_path)
    os.mkfifo(fifo_out_path)
    print("Initializing playback stream...")
    process_handle_playback = subprocess.Popen(["aplay", "-f", "cd", fifo_out_path])
    fifo_out = utils.open_with_flag(fifo_out_path, os.O_WRONLY, "wb")
    
    print("Connecting to host")
    sock.connect((HOST, PORT))
    print("Connected")
    sock_open = True
    print("Initializing input stream...")
    process_handle_record = subprocess.Popen(["ffmpeg", "-y"] + 
                                             cfg.ffmpeg_client_in + 
                                             ["-ar", "44100", "-ac", "2", "-f", "wav", fifo_in_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
        )
    fifo_in = utils.open_with_flag(fifo_in_path, os.O_RDONLY, "rb")
    
    st = threading.Thread(target=send_thread, args=(fifo_in,))
    rt = threading.Thread(target=recv_thread, args=(fifo_out,))
    st.start()
    rt.start()
    print("initialized")
    st.join()
    rt.join()

def close_resources():
    global sock_open
    global process_handle_record
    global process_handle_playback
    sock.close()
    sock_open = False
    if process_handle_record != None:
        process_handle_record.kill()
    if process_handle_playback != None:
        process_handle_playback.kill()
    process_handle_playback = None
    process_handle_record = None

def handle_int(sig, frame):
    global g_do_exit
    close_resources()
    print("Exiting...")
    g_do_exit = True
    sys.exit(0)

signal.signal(signal.SIGINT, handle_int)

if __name__ == "__main__":
    while True:
        try:
            main()
        except:
            continue
        if g_do_exit:
            break
        close_resources()
        print("Retrying in 1s")
        time.sleep(1)
