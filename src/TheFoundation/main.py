import os
import time
import socket
import network

try:
    import usys as sys
except:
    import sys

try:
    import ubinascii as binascii
except:
    import binascii

try:
    import uhashlib as hashlib
except:
    import hashlib


from websocket import websocket


DEBUG = 1

def server_handshake(sock):
    clr = sock.makefile("rwb", 0)
    l = clr.readline()
    # sys.stdout.write(repr(l))

    webkey = None

    while 1:
        l = clr.readline()
        if not l:
            raise OSError("EOF in headers")
        if l == b"\r\n":
            break
        #    sys.stdout.write(l)
        h, v = [x.strip() for x in l.split(b":", 1)]
        if DEBUG:
            print((h, v))
        if h == b"Sec-WebSocket-Key":
            webkey = v

    if not webkey:
        raise OSError("Not a websocket request")

    if DEBUG:
        print("Sec-WebSocket-Key:", webkey, len(webkey))

    d = hashlib.sha1(webkey)
    d.update(b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11")
    respkey = d.digest()
    respkey = binascii.b2a_base64(respkey)[:-1]
    if DEBUG:
        print("respkey:", respkey)

    sock.send(
        b"""\
HTTP/1.1 101 Switching Protocols\r
Upgrade: websocket\r
Connection: Upgrade\r
Sec-WebSocket-Accept: """
    )
    sock.send(respkey)
    sock.send("\r\n\r\n")


# Very simplified client handshake, works for MicroPython's
# websocket server implementation, but probably not for other
# servers.
def client_handshake(sock):
    cl = sock.makefile("rwb", 0)
    cl.write(
        b"""\
GET / HTTP/1.1\r
Host: echo.websocket.org\r
Connection: Upgrade\r
Upgrade: websocket\r
Sec-WebSocket-Key: foo\r
\r
"""
    )
    l = cl.readline()
    #    print(l)
    while 1:
        l = cl.readline()
        if l == b"\r\n":
            break



class ClientClosedError(Exception):
    pass


class WebSocketConnection:
    def __init__(self, addr, s, close_callback):
        self.client_close = False
        self._need_check = False

        self.address = addr
        self.socket = s
        self.ws = websocket(s, True)
        self.close_callback = close_callback

        s.setblocking(False)
        s.setsockopt(socket.SOL_SOCKET, 20, self.notify)

    def notify(self, s):
        self._need_check = True

    def read(self):
        if self._need_check:
            self._check_socket_state()

        msg_bytes = None
        try:
            msg_bytes = self.ws.read()
        except OSError:
            self.client_close = True

        if not msg_bytes and self.client_close:
            raise ClientClosedError()

        return msg_bytes

    def write(self, msg):
        try:
            self.ws.write(msg)
        except OSError:
            self.client_close = True

    def _check_socket_state(self):
        self._need_check = False
        sock_str = str(self.socket)
        state_str = sock_str.split(" ")[1]
        state = int(state_str.split("=")[1])

        if state == 4:
            self.client_close = True

    def is_closed(self):
        return self.socket is None

    def close(self):
        print("Closing connection.")
        self.socket.setsockopt(socket.SOL_SOCKET, 20, None)
        self.socket.close()
        self.socket = None
        self.ws = None

        if self.close_callback:
            self.close_callback(self)







class WebSocketClient:
    def __init__(self, conn: WebSocketConnection):
        self.connection: WebSocketConnection = conn

    def process(self):
        if (message := self.connection.read()) is not None:
            print(message)
            self.connection.write('Pong')


class WebSocketServer:

    def __init__(self, page, max_connections=1):
        self._listen_s = None
        self._clients = []
        self._max_connections = max_connections
        self._page = page

    def _setup_conn(self, port, accept_handler):
        self._listen_s = socket.socket()
        self._listen_s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        ai = socket.getaddrinfo("0.0.0.0", port)
        addr = ai[0][4]

        self._listen_s.bind(addr)
        self._listen_s.listen(1)

        if accept_handler:
            self._listen_s.setsockopt(socket.SOL_SOCKET, 20, accept_handler)

        for i in (network.AP_IF, network.STA_IF):
            iface = network.WLAN(i)

            if iface.active():
                print("WebSocket started on ws://%s:%d" % (iface.ifconfig()[0], port))

    def _accept_conn(self, listen_sock):
        cl, remote_addr = listen_sock.accept()
        print("Client connection from:", remote_addr)

        if len(self._clients) >= self._max_connections:
            # Maximum connections limit reached
            cl.setblocking(True)
            cl.sendall("HTTP/1.1 503 Too many connections\n\n")
            cl.sendall("\n")
            #TODO: Make sure the data is sent before closing
            time.sleep(0.1)
            cl.close()
            return

        try:
            server_handshake(cl)
        except OSError:
            # Not a websocket connection, serve webpage
            self._serve_page(cl)
            return

        self._clients.append(self._make_client(WebSocketConnection(remote_addr, cl, self.remove_connection)))

    def _make_client(self, conn: WebSocketConnection):
        return WebSocketClient(conn)

    def _serve_page(self, sock):
        try:
            sock.sendall('HTTP/1.1 200 OK\nConnection: close\nServer: WebSocket Server\nContent-Type: text/html\n')
            length = os.stat(self._page)[6]
            sock.sendall('Content-Length: {}\n\n'.format(length))
            # Process page by lines to avoid large strings
            with open(self._page, 'r') as f:
                for line in f:
                    sock.sendall(line)
        except OSError:
            # Error while serving webpage
            pass
        sock.close()

    def stop(self):
        if self._listen_s:
            self._listen_s.close()
        self._listen_s = None
        for client in self._clients:
            client.connection.close()
        print("Stopped WebSocket server.")

    def start(self, port=80):
        if self._listen_s:
            self.stop()
        self._setup_conn(port, self._accept_conn)
        print("Started WebSocket server.")

    def process_all(self):
        for client in self._clients:
            client.process()

    def remove_connection(self, conn):
        for client in self._clients:
            if client.connection is conn:
                self._clients.remove(client)
                return
            


def network_connect(ssid: str, password: str):
    wlan = network.WLAN(network.STA_IF)
    # activate the interface
    wlan.active(True)
    # connect to the access point with the ssid and password
    wlan.connect(ssid, password)

    for c in range(0, 5):
        time.sleep(1)

        if wlan.status() < 0 or wlan.status() >= 3:
            break

    if wlan.isconnected() == False:
        raise RuntimeError('Connection failed to WiFi')
    else:
        ifconfig = wlan.ifconfig()
        print(s := f'Connection succeeded to WiFi = {ssid} with IP = {ifconfig[0]}')
        print('-' * len(s))


network_connect("PMD", "Primadiag2021'...")

ws = WebSocketServer(' ... ', 2)
ws.start()


while True:
    ws.process_all()
    