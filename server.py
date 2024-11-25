import socket
import ssl
import threading
import time
import os
import shutil
import subprocess
import hashlib
import utils
import cfg
import sys
import signal

HOST = "0.0.0.0"
PORT = 14880

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

pipes_path = cfg.fifo_pipes_root + "server_pipes/pipes/"
key_base = "/etc/letsencrypt/live/mana.kyun.li"
keyfile = key_base + "/privkey.pem"
certfile = key_base + "/fullchain.pem"


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
recv_in_ready = False



def make_addr_key(addr): 
    return str(addr).replace("'", "_").replace(" ", "_").replace(",", "_").replace("(", "_").replace(")", "_")

def muxer_loop(out_pipe):
    global muxout_buf
    global muxout_buffer_ready
    muxout_buffer_ready = False
    #print("Muxing")
    muxout_buf = out_pipe.read(cfg.buffer_size)
    #print("buffer ready")
    muxout_buffer_ready = True

def start_mux():
    global recv_in_ready
    command = ["ffmpeg", "-y",]
    print("5 seconds until mux process starts")
    time.sleep(5)
    #iterate all clients
    clients_lsdir = os.listdir(pipes_path)
    clients_lsdir.remove(muxout_path)
    print(clients_lsdir)
    for client_pipe in clients_lsdir:
        command += ["-i", pipes_path + client_pipe]

    if len(clients_lsdir) > 1:
        command += [
        "-filter_complex",
        f"amerge=inputs={len(clients_lsdir)}",
        ]
    #audio channel
    command += ["-ac", "1"]
    #sample rate
    command += ["-ar", "44100"]
    #sample format
    #command += ["-sample-fmt", "s16"]
    command += ["-f", "wav", pipes_path + muxout_path]
    
    print("starting mux subproc, stopped accepting new clients(lol)")
    print("Running command: ")
    print(command)
    recv_in_ready = True
    subprocess.run(command)

def clients_ready():
    for v in client_mux_syncset.values():
        if not v:
            return False
    return True
def wait_client_mux():
    while not clients_ready():
        time.sleep(0.005)
    muxout_buffer_ready = False
    for k in client_mux_syncset.keys():
        client_mux_syncset[k] = False
    
def muxer_proc():
    #init
    #do not open here, since this will block until
    #write happens
    utils.mkfifo(pipes_path + muxout_path, os.O_RDONLY, True)
    smux_thread = threading.Thread(target=start_mux)
    smux_thread.start()
    out_pipe = open(pipes_path + muxout_path, "rb")
    while True:
        muxer_loop(out_pipe)
        wait_client_mux()



def worker_send(conn, addr):
    global muxout_buf
    global muxout_buffer_ready
    while True:
        while ((not muxout_buffer_ready) or client_mux_syncset[addr]):
            time.sleep(0.005)
            
        conn.send(muxout_buf)
        client_mux_syncset[addr] = True
        #print("send data with hash " + hashlib.sha256(muxout_buf).hexdigest())
        

def worker_recv(conn, addr):
    global client_recv_fifos
    while not recv_in_ready:
        #sleep longer to wait for ffmpeg to open pipe
        
        time.sleep(0.1)
    client_recv_fifos[addr] = open(pipes_path + addr, "wb")

    while True:
        data = conn.read(cfg.buffer_size)
        if not data:
            return
        #send data to fifo
        #print(client_recv_fifos)
        #print("Writing to muxer")
        
        
        client_recv_fifos[addr].write(data)
    
def worker_init(conn : ssl.SSLSocket, addr):
    global client_recv_fifos
    global recv_in_ready
    #deny new clients
    if(recv_in_ready):
        conn.close()
        return
    #add client
    print("new client: " + addr)
    client_mux_syncset[addr] = True
    client_recv_fifos[addr] = utils.mkfifo(pipes_path + addr, os.O_WRONLY, False)
    #TODO: thread handler
    send_thread = threading.Thread(target=worker_send, args=(conn, addr))
    recv_thread = threading.Thread(target=worker_recv, args=(conn, addr))
    send_thread.start()
    recv_thread.start()
    print("client initialized")

def muxer_init():
    mux_thread = threading.Thread(target=muxer_proc)
    mux_thread.start()


def handle_int(sig, frame):
    sock_open = False
    print("Exiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_int)

if __name__ == "__main__":
    server.bind((HOST, PORT))
    server.listen(0)
    shutil.rmtree(pipes_path, ignore_errors=True)
    os.makedirs(pipes_path, exist_ok=True)
    muxer_init()
    while True:
        connection, client_address = server.accept()
        worker_init(connection, make_addr_key(client_address))

