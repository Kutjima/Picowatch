import gc
import os
import re
import time
import json
import socket
import machine
import network
import uasyncio as asyncio


class Response():

    RESPONSE_OK: int = 200
    RESPONSE_NOT_FOUND: int = 404

    def __init__(self, url: str, method: str, params: dict, match):
        self.content: str = ''
        self.headers: list = []

        self.url: str = url
        self.method: str = method
        self.params: dict = params
        self.payload: dict = {}


class RouterHTTP:
    
    def __init__(self, ssid: str, password: str):
        self.led = machine.Pin('LED', machine.Pin.OUT)
        self.patterns  = {}
        self.status_codes = {}

        self.wlan = network.WLAN(network.STA_IF)
        # activate the interface
        self.wlan.active(True)
        # connect to the access point with the ssid and password
        self.wlan.connect(ssid, password)

        for c in range(0, 3):
            if self.wlan.status() < 0 or self.wlan.status() >= 3:
                break

            time.sleep(1)

        if self.wlan.isconnected() == False:
            raise RuntimeError('Connection failed to WiFi')
        else:
            self.ifconfig = self.wlan.ifconfig()
            print(f'Connection succeeded to WiFi = {ssid} with IP = {self.ifconfig[0]}')

    def map(self, methods: str, pattern: str, callback: callable):
        if str(methods).isdigit():
            self.status_codes[methods] = callback
        else:
            self.patterns[pattern] = (list(map(lambda s: s.strip(), methods.upper().split('|'))), callback)

    def listen(self, port: int = 8080, ws_buffsize: int = 256, ws_backlog: int = 100):
        # HTTP server with socket
        self.ws = socket.socket()
        
        self.ws.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ws.bind(bind_to := socket.getaddrinfo(self.ifconfig[0], port)[0][-1])
        self.ws.listen(ws_backlog)
        print(f'Listening on = {bind_to[0]}:{bind_to[1]}')

        while True:
            try:
                gc.collect()

                url: str = ''
                method: str = 'GET'
                params: dict = {}
                headers: dict = {}
                status_code: int = Response.RESPONSE_NOT_FOUND
                connection, _ = self.ws.accept()

                for i, h in enumerate(connection.recv(ws_buffsize).split(b'\r\n')):
                    h = bytes(h).decode('utf-8')
                    
                    if i == 0:
                        if (match := re.compile(r'(GET|POST)\s+([^\s]+)\s+HTTP').search(h)):
                            if len(uu := match.group(2).split('?')) == 2:
                                for pp in uu[1].split('&'):
                                    if len(p := pp.split('=')) == 2:
                                        params[self.decode(p[0])] = self.decode(p[1])

                            url = uu[0]
                            method = match.group(1)
                    elif len(h := h.split(': ')) == 2:
                        headers[h[0]] = h[1]

                for pattern, item in self.patterns.items():
                    if method not in item[0]:
                        continue

                    if pattern == url or (match := re.compile(pattern).search(url)):
                        if (status_code := item[1](response := Response(url, method, params, match))) == Response.RESPONSE_OK:
                            [connection.send(f'{h}\r\n') for h in response.headers]
                            connection.send(response.content)
                            print(Response.RESPONSE_OK, pattern, url, match)
                    
                connection.close()
            except OSError as e:
                connection.close()

    @staticmethod
    def decode(encoded: str):
        i = 0
        decoded: str = ''

        while i < len(encoded):
            if encoded[i] == '%':
                decoded += chr(int(encoded[i + 1:i + 3], 16))
                i += 3
            else:
                decoded += encoded[i]
                i += 1

        return decoded

    

rhttp = RouterHTTP('SFR-a9c8', 'abc123de45f6')

def a(response: Response) -> int:
    if response.url == '/hello/world':
        time.sleep(5)

    return Response.RESPONSE_OK
    

rhttp.map(404, '', a)
rhttp.map('GET', '/hello/world', a)
rhttp.map('GET', '^/hello/(\w+)/off', a)
rhttp.map('GET|POST', '/^online/article/([a-z0-9\-]{1,19})/([0-9]{1,9})$/i', a)
rhttp.map('GET', '/^profile/([a-z0-9\-]{3,})$/i', a)

rhttp.listen()