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


MUXOUT_PATH = "muxed_out"
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile, keyfile)
server = context.wrap_socket(
    server, server_side=True
)
muxout_buf = b""
muxout_buffer_ready = False
recv_in_ready = False



def start_mux(clients : list, muxin_base_path : str, muxout_path : str) -> None:
    command = ["ffmpeg", "-y"]
    
    #sample rate in
    #command += ["-sample_rate", "44100"]
    command += ["-f", "wav"]
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
    subprocess.Popen(command,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL
                     )


g_all_clients : dict[str, Client] = {}
g_accept_conns : bool = True
g_first_conn : bool = False
class Client:
    def __init__(self, conn : ssl.SSLSocket, addr_key : str):
        self.addr_key = addr_key
        self.socket = conn
        self.client_pipe_root = pipes_path + self.addr_key + "/"
        self.muxout_path : str = self.client_pipe_root + MUXOUT_PATH
        self.pipe_broken = False

        os.makedirs(self.client_pipe_root, exist_ok=True)


        #NEEDS INIT
        self.sender_pipes : dict[str, _io.BufferedWriter] = {}
        self.sender_pipe_paths : dict[str, str] = {}
        self.muxout_pipe : _io.BufferedReader = None
        
        
    def write_buffer(self, client_addr, buffer : bytes):
        self.sender_pipes[client_addr].write(buffer)
    
    def on_recv(self, buffer : bytes):
        global g_all_clients
        #echo to all buffers
        for client in g_all_clients.values():
            if client.addr_key == self.addr_key:
                continue
            client.write_buffer(self.addr_key, buffer)
    
    def send_loop(self):
        while not self.pipe_broken:
            data = self.muxout_pipe.read(cfg.buffer_size)
            self.socket.send(data)
    
    def recv_loop(self):
        while not self.pipe_broken:
            data = self.socket.recv(cfg.buffer_size)
            if not data:
                self.pipe_broken = True
            self.on_recv(data)
        
    def reload_mux(self):
        start_mux(self.sender_pipes.keys(), self.client_pipe_root, self.muxout_path)
    
    def load_clients(self):
        for client in g_all_clients.values():
            if client.addr_key == self.addr_key:
                continue
            self.sender_pipe_paths[client.addr_key] = self.client_pipe_root + client.addr_key
            
        
        
    def open_pipes(self):
        #pipe for other clients
        for sender_key, fifo_path in self.sender_pipe_paths.items():
            #open sender pipes
            #we need rw in order to not have conflicts
            #but this is write only, ffmpeg will read from this
            self.sender_pipes[sender_key] = utils.mkfifo_open(fifo_path, os.O_RDWR, "wb")
        #pipe for muxout
        self.muxout_pipe = utils.mkfifo_open(self.muxout_path, os.O_RDWR, "rb")
    
    def start_threads(self) -> list:
        recv = threading.Thread(target=self.recv_loop)
        send = threading.Thread(target=self.send_loop)
        recv.start()
        send.start()
        return [recv, send]
            
    def init_first(self):
        self.load_clients()
        self.open_pipes()

    def init_final(self):
        self.reload_mux()
        self.start_threads()

def handle_int(sig, frame):
    sock_open = False
    print("Exiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_int)


def accept_conns():
    global g_first_conn
    global g_accept_conns
    while True:
        connection, client_address = server.accept()
        g_first_conn = True
        if not g_accept_conns:
            connection.close()
            return
        addr_key = utils.make_addr_key(client_address)
        
        print(f"New client: {addr_key}")
        g_all_clients[addr_key] = Client(connection, addr_key)


def main():
    global g_accept_conns
    global g_first_conn
    server.bind((HOST, PORT))
    server.listen(0)
    shutil.rmtree(pipes_path, ignore_errors=True)
    os.makedirs(pipes_path, exist_ok=True)
    print("Listening...")

    accept_thread = threading.Thread(target=accept_conns)
    accept_thread.start()
    while not g_first_conn:
        time.sleep(0.1)
    time.sleep(cfg.server_sleep_time)
    g_accept_conns = False
    print("Now no longer accepting new connections. initializing...")
    for v in g_all_clients.values():
        v.init_first()
    for v in g_all_clients.values():
        v.init_final()
    
    print("Finished initialization of clients.")
    while True:
        time.sleep(10)



if __name__ == "__main__":
    main()