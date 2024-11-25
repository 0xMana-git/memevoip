import socket
import ssl
import threading
import time
import os
import shutil
HOST = "0.0.0.0"
PORT = 14880

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

pipes_path = "pipes/"
key_base = "/etc/letsencrypt/live/mana.kyun.li"
keyfile = key_base + "/privkey.pem"
certfile = key_base + "/fullchain.pem"
#4kb
buffer_size = 1024 * 4
muxout_path = "muxed_out"
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile, keyfile)
server = context.wrap_socket(
    server, server_side=True
)

muxout_buffer_ready = False
client_muxes = {}
client_mux_syncset = {}
client_recv_fifos = {}

def mkfifo(fpath, open_mode):
    os.mkfifo(fpath, 0o600)
    return open(fpath, open_mode)

def muxer_loop(out_pipe):
    global muxout_buffer_ready
    muxout_buffer_ready = false
    muxout_buf = out_pipe.read(buffer_size)
    muxout_buffer_ready = true

def muxer_proc():
    #init
    out_pipe = mkfifo(pipe_paths + muxout_path, "rb")
    while True:
        muxer_loop(out_pipe)
        wait_client_mux()



def worker_send(conn, addr):
    global muxout_buffer_ready
    while(not muxout_buffer_ready):
        time.sleep(0.01)
    conn.send(muxout_buf)
    client_mux_syncset[addr] = True

def worker_recv(conn, addr, fifo_recv):
    global client_recv_fifos
    data = conn.read(buffer_size)
    #send data to fifo
    print(client_recv_fifos)
    client_recv_fifos[addr].write(data)
    
def worker_init(conn, addr):
    global client_recv_fifos
    #add client
    print("new client: " + addr)
    client_mux_syncset[addr] = True
    client_recv_fifos[addr] = mkfifo(pipes_path + addr, "wb")
    #TODO: thread handler
    send_thread = threading.Thread(target=worker_send, args=(conn, addr))
    recv_thread = threading.Thread(target=worker_recv, args=(conn, addr, client_recv_fifos[addr]))
    send_thread.start()
    recv_thread.start()

if __name__ == "__main__":
    server.bind((HOST, PORT))
    server.listen(0)
    shutil.rmtree(pipes_path, ignore_errors=True)
    os.makedirs(pipes_path, exist_ok=True)
    while True:
        connection, client_address = server.accept()
        worker_init(connection, str(client_address))

