import ssl
import os
import threading


fifo_in_path = "audio_in"
fifo_out_path = "audio_out"

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)

host, port = "mana.kyun.li", "14880"
pipe_paths = "pipes/"
key_base = "/etc/letsencrypt/live/mana.kyun.li"
keyfile = key_base + "/privkey.pem"
certfile = key_base + "/fullchain.pem"
#4kb
buffer_size = 1024 * 4
muxout_path = "muxed_out"
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
client = context.wrap_socket(sock)


def send_thread(fifo):
    while True:
        buffer_send = fifo.read(buffer_size)
        sock.send(buffer_send)
def recv_thread(fifo):
    while True:
        buffer_recv = sock.recv(buffer_size)
        fifo.write(buffer_recv)
def main():
    fifo_in = open(fifo_in_path, "rb")
    fifo_out = open(fifo_out_path, "wb")
    sock.connect((host, port))
    st = threading.Thread(send_thread, (fifo_in))
    rt = threading.Thread(recv_thread, (fifo_out))
    st.start()
    rt.start()
    st.join()
    rt.join()
