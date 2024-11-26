from __future__ import annotations
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

import _io
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



def start_mux(clients : list, muxin_base_path : str, muxout_path : str) -> None:
    command = ["ffmpeg", "-y"]
    
    #sample rate in
    command += ["-ar", "44100"]
    #audio channel in
    command += ["-ac", "2"]
    for client_pipe in clients:
        command += ["-i", muxin_base_path + client_pipe]

    if len(clients) > 1:
        command += ["-filter_complex",f"amerge=inputs={len(clients)}"]
    #audio channel out
    command += ["-ac", "2"]
    #sample rate out
    command += ["-ar", "44100"]
    #sample format
    #command += ["-sample-fmt", "s16"]
    command += ["-f", "wav", muxout_path]
    
    print("starting mux subproc, stopped accepting new clients(lol)")
    print("Running command: ")
    print(command)
    subprocess.Popen(command)


g_all_clients : dict[str, Client]= {}

class Client:
    def __init__(self, conn : ssl.SSLSocket, addr_key : str):
        self.addr_key = addr_key
        self.socket = conn
        self.client_pipe_root = pipes_path + self.addr_key + "/"
        os.makedirs(self.client_pipe_root, exist_ok=True)
        self.send_ready = False
        self.muxout_buf = b""
        self.client_pipes : dict[str, _io.BufferedWriter] = {}
        self.muxout_pipe : _io.BufferedReader = None
        self.pipe_broken = False
    def write_buffer(self, client_addr, buffer : bytes):
        self.client_pipes[client_addr].write(buffer)
    
    def on_recv(self, buffer : bytes):
        global g_all_clients
        #echo to all buffers
        for client in g_all_clients.values():
            client.write_buffer(self.addr_key, buffer)
    
    def send_loop(self):
        while True:
            data = self.muxout_pipe.read(cfg.buffer_size)
            self.socket.send(data)
    
    def recv_loop(self):
        while True:
            data = self.socket.recv(cfg.buffer_size)
            if not data:
                self.pipe_broken = True
            self.on_recv(data)
        
    def reload_mux():
        pass
    

 





def muxer_loop(out_pipe):
    global muxout_buf
    global muxout_buffer_ready
    muxout_buffer_ready = False
    muxout_buf = out_pipe.read(cfg.buffer_size)
    muxout_buffer_ready = True


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

    mux_out_full = pipes_path + muxout_path

    print(f"{cfg.server_sleep_time} seconds until mux process starts")
    time.sleep(cfg.server_sleep_time)

    clients_lsdir = os.listdir(pipes_path)
    clients_lsdir.remove(muxout_path)
    print(f"Clients: {str(clients_lsdir)}")

    utils.mkfifo(mux_out_full, os.O_RDONLY, False)
    start_mux(clients_lsdir, pipes_path, mux_out_full)

    print(f"opening {mux_out_full}")
    out_pipe = open(mux_out_full, "rb")
    print("opened")
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
    client_recv_fifos[addr] = utils.open_with_flag(pipes_path + addr, os.O_RDWR, "wb")

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
    muxer_did_init = False
    print("Listening...")
    while True:
        connection, client_address = server.accept()
        worker_init(connection, utils.make_addr_key(client_address))
        if not muxer_did_init:
            muxer_init()
            muxer_did_init = True

