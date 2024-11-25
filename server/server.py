import socket
import ssl
import threading
import time
import os
import shutil
import subprocess
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
muxout_buf = b""
muxout_buffer_ready = False
client_muxes = {}
client_mux_syncset = {}
client_recv_fifos = {}

def mkfifo(fpath, open_mode, do_open=True):
    os.mkfifo(fpath, 0o600)
    if do_open:
        return open(fpath, open_mode)

def make_addr_key(addr):
    return str(addr).replace("'", "=").replace(" ", "_").replace(",", "_")

def muxer_loop(out_pipe):
    global muxout_buffer_ready
    muxout_buffer_ready = False
    muxout_buf = out_pipe.read(buffer_size)
    muxout_buffer_ready = True

def start_mux():
    command = ["ffmpeg", "-y",]
    print("5 seconds until mux process starts")
    time.sleep(5)
    #iterate all clients
    clients_lsdir = os.listdir(pipes_path)
    clients_lsdir.remove(muxout_path)
    print(clients_lsdir)
    for client_pipe in clients_lsdir:
        command += ["-i", client_pipe]

    if len(clients_lsdir) > 1:
        command += [
        "-filter_complex",
        f"amerge=inputs={len(clients_lsdir)}",
        "-ac", "2"]
    command += ["-f", "flac", pipes_path + muxout_path]
    
    print("starting mux subproc, stopped accepting new clients(lol)")
    print("Running command: ")
    print(command)
    subprocess.run(command)


def clients_ready():
    for v in client_mux_syncset.values():
        if not v:
            return False
    return True
def wait_client_mux():
    while not clients_ready():
        time.sleep(0.01)
    for k in client_mux_syncset.keys():
        client_mux_syncset[k] = False
    
def muxer_proc():
    #init
    #do not open here, since this will block until
    #write happens
    mkfifo(pipes_path + muxout_path, "rb", False)
    smux_thread = threading.Thread(target=start_mux)
    smux_thread.start()
    out_pipe = open(pipes_path + muxout_path, "rb")
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

def muxer_init():
    mux_thread = threading.Thread(target=muxer_proc)
    mux_thread.start()
if __name__ == "__main__":
    server.bind((HOST, PORT))
    server.listen(0)
    shutil.rmtree(pipes_path, ignore_errors=True)
    os.makedirs(pipes_path, exist_ok=True)
    muxer_init()
    while True:
        connection, client_address = server.accept()
        worker_init(connection, make_addr_key(client_address))

