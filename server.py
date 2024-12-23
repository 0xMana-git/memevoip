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
import traceback

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

subprocs : list[subprocess.Popen]= []

def start_mux(clients : list, muxin_base_path : str, muxout_path : str) -> None:
    command = ["ffmpeg", "-y", "-fflags", "+discardcorrupt"]
    
    #sample rate in
    #command += ["-sample_rate", "44100"]
    #command += ["-f", "wav"]
    #audio channel in
    #command += ["-ac", "2"]
    for client_pipe in clients:
        command += ["-i", muxin_base_path + client_pipe]
    
    
    command += ["-filter_complex"]
    filter_command = ""
    inputs_len = len(clients)

    for i in range(inputs_len):
        filter_command += f"[{i}]"
        filter_command += "atrim=0"
        filter_command += f"[a{i}];"
    for i in range(inputs_len):
        filter_command += f"[a{i}]"
        
    filter_command += f"amix=inputs={inputs_len}:duration=longest"
    command += [filter_command]
    #audio channel out
    command += ["-ac", "2"]
    #sample rate out
    command += ["-ar", "48000"]
    #sample format
    #command += ["-sample-fmt", "s16"]
    command += ["-f", "flac", muxout_path]
    
    print("Running command: ")
    print(command)

    p = subprocess.Popen(command,
       stderr=subprocess.DEVNULL,
       stdout=subprocess.DEVNULL
                     )
    subprocs.append(p)


def probe_file(filename):
    print("testing")
    cmd = ['ffprobe', '-show_format', '-pretty', '-loglevel', 'quiet', filename]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(filename)
    out, err =  p.communicate()
    print (out)
    if err:
        print (err)
    print(p.returncode)
    return (out, err, p.returncode)

def probe_buffer(buffer : bytes):
    cmd = ['ffprobe', '-show_format', '-pretty', "-"]
    p : subprocess.Popen = subprocess.Popen(cmd, stdin=subprocess.PIPE
                                            , stdout=subprocess.PIPE, stderr=subprocess.PIPE
                                            )
    p.stdin.write(buffer)
    out, err =  p.communicate()
    return (out, err, p.returncode)

    

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
        self.recv_eof : bool = False
        self.is_valid_sender = True

        os.makedirs(self.client_pipe_root, exist_ok=True)


        #NEEDS INIT
        self.test_buffer = None
        #list of clients to write to
        self.recievers : set = set()
        #other clients will write to these pipes
        self.sender_pipes : dict[str, _io.BufferedWriter] = {}
        self.sender_pipe_paths : dict[str, str] = {}
        self.muxout_pipe : _io.BufferedReader = None

    
    def debug_print(self, msg):
        print(f"[CLIENT] {self.addr_key}: {msg}")
        
        
    def write_buffer(self, client_addr, buffer : bytes):
        self.sender_pipes[client_addr].write(buffer)
    
    def write_to_test_buf(self):
        self.test_buffer = self.socket.recv(cfg.buffer_size)
        if not self.test_buffer:
            self.pipe_broken = True

    def test_client(self):
        #write to test
        self.write_to_test_buf()
        #ffprobe test
        out, err, rcode = probe_buffer(self.test_buffer)
        if rcode != 0:
            print(f"{self.addr_key} is an invalid sender")
            self.is_valid_sender = False

    
    def on_recv(self, buffer : bytes):
        global g_all_clients
        if not self.is_valid_sender:
            return
        #echo to all buffers
        for client in self.recievers:
            if client.addr_key == self.addr_key:
                continue
            client.write_buffer(self.addr_key, buffer)
    
    #TODO: fix encodes breaking when u stop sending data to server
    def send_loop(self):
        try:
            while not self.pipe_broken:
                data = self.muxout_pipe.read(cfg.buffer_size)
                self.socket.send(data)
        except Exception as e:
            self.debug_print("send socket broken ")
            self.pipe_broken = True
            return
        
    def recv_loop(self):
        while not self.pipe_broken and not self.recv_eof:
            if self.test_buffer == None:
                data = self.socket.recv(cfg.buffer_size)
            else:
                data = self.test_buffer
                self.test_buffer = None
            if not data:
                self.recv_eof = True
                break
            self.on_recv(data)
        self.debug_print("recv socket broken/eof")
        self.close_sent_to_pipes()
        
    def reload_mux(self):
        start_mux(self.sender_pipes.keys(), self.client_pipe_root, self.muxout_path)
    
    def load_clients(self):
        for client in g_all_clients.values():
            if client.addr_key == self.addr_key:
                continue
            if not client.is_valid_sender:
                continue
            self.recievers.add(client)
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
    
    def close_sent_to_pipes(self):
        for c in self.recievers:
            c.sender_pipes[self.addr_key].close()
        #maybe dont close this pipe
        #self.muxout_pipe.close()
    
    def start_threads(self) -> list:
        return [utils.start_daemon_thread(self.recv_loop), utils.start_daemon_thread(self.send_loop)]
            
    def init_first(self):
        self.load_clients()
        self.open_pipes()

    def init_final(self):
        self.reload_mux()
        self.start_threads()

def handle_int(sig, frame):
    sock_open = False
    for p in subprocs:
        p.kill()
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

    accept_thread = utils.start_daemon_thread(accept_conns)
    while not g_first_conn:
        time.sleep(0.1)
    time.sleep(cfg.server_sleep_time)
    g_accept_conns = False
    print("Now no longer accepting new connections. initializing...")
    test_threads = []
    for v in g_all_clients.values():
        t = threading.Thread(v.test_client())
        test_threads.append(t)
        t.start()
    for t in test_threads:
        t.join()

    for v in g_all_clients.values():
        v.init_first()
    for v in g_all_clients.values():
        v.init_final()
    
    print("Finished initialization of clients.")
    while True:
        time.sleep(10)



if __name__ == "__main__":
    main()