import ssl
import os
import threading
import socket
import logging
import signal
import sys


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



def send_thread(fifo):
    global sock_open
    while sock_open:
        buffer_send = fifo.read(buffer_size)
        sock.send(buffer_send)
        print("sent bufsize")
def recv_thread(fifo):
    global sock_open
    while sock_open:
        buffer_recv = sock.recv(buffer_size)
        if not data:
            sock_open = False
            print("EOF reached")
            return
        fifo.write(buffer_recv)
        print("recv bufsize")

def main():
    fifo_in = open(fifo_in_path, "rb")
    fifo_out = open(fifo_out_path, "wb")
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
    print("Exiting...")
    sys.exit(0)
signal.signal(signal.SIGINT, handle_int)

if __name__ == "__main__":
    main()
