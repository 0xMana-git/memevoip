import socket
import ssl
import threading
import time
import os
HOST = "0.0.0.0"
PORT = 14880

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

pipe_paths = "pipes/"
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


client_muxes = {}


def muxer_loop(out_pipe):
    muxout_buffer_ready = false
    muxout_buf = out_pipe.read(buffer_size)
    muxout_buffer_ready = true

def muxer_proc():
    #init
    out_pipe = os.mkfifo(pipe_paths + muxout_path, 0o600)
    while True:
        muxer_loop(out_pipe)
        wait_client_mux()
    

def worker_send(conn, addr):
    
    while(not muxout_buffer_ready):
        time.sleep(0.01)
    conn.send(muxout_buf)
    client_mux_syncset[addr] = True

def worker_recv(conn, addr, fifo_recv):
    data = conn.read(buf_size)
    #send data to fifo
    client_recv_fifos[addr].write(data)
    
def worker_init(conn, addr):
    #add client
    client_mux_syncset[addr] = True
    client_recv_fifos[addr] = os.mkfifo(pipes_path + addr, 0o600)
    #TODO: thread handler
    send_thread = threading.Thread(worker_send,(conn, addr))
    recv_thread = threading.Thread(worker_recv,(conn, addr))
    send_thread.start()
    recv_thread.start()

if __name__ == "__main__":
    server.bind((HOST, PORT))
    server.listen(0)

    while True:
        connection, client_address = server.accept()
        worker_init(connection, client_address)

