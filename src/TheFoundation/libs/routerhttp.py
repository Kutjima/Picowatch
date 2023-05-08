import gc
import os
import re
import time
import machine
import network
import uasyncio as asyncio


led = machine.Pin('LED', machine.Pin.OUT)


class RouterHttp():

    def __init__(self, ssid: str, password: str):
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

    def listen(self, port: int = 80):
        asyncio.run(self.start_server(port))

    def listen_with_background_task(self, background_task: callable, port: int = 80):
        if not callable(background_task):
            raise TypeError('background_task must be callable')
        
        async def serve_forever():
            await asyncio.gather(self.start_server(port), background_task())
        
        asyncio.run(serve_forever())

    def map(self, methods: str, pattern: str, callback: callable):
        if str(methods).isdigit():
            self.status_codes[methods] = callback
        else:
            self.patterns[pattern] = (list(map(lambda s: s.strip(), methods.upper().split('|'))), callback)

    async def start_server(self, port: int = 80):
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
        
        async def client_callback(reader: asyncio.StreamReader, writer: asyncio.asyncioStreamWriter):
            gc.collect()

            try:
                response = RouterHttp.Response()
                status_code = response.RESPONSE_NOT_FOUND

                while True:
                    if (line := (await reader.readline()).decode('utf-8').strip()) == '':
                        break
                    
                    if len(response.headers) == 0:
                        if (match := re.compile(r'(GET|POST)\s+([^\s]+)\s+HTTP').search(line)):
                            if len(uu := match.group(2).split('?')) == 2:
                                for pp in uu[1].split('&'):
                                    if len(p := pp.split('=')) == 2:
                                        response.params[decode(p[0])] = decode(p[1])

                            response.url = uu[0]
                            response.method = match.group(1)
                    else:
                        response.headers.append(line)

                if not response.url:
                    return

                for pattern, item in self.patterns.items():
                    if response.method not in item[0]:
                        continue

                    if pattern == response.url or (match := re.compile(pattern).search(response.url)):
                        status_code = item[1](response) or response.RESPONSE_NO_CONTENT

                if status_code in self.status_codes:
                    self.status_codes[status_code](response)

                return await response.send(writer, status_code)
            except OSError as e:
                print(f'RouterHttp.client_callback(): {e}')
                writer.close()

        shutdown_event = asyncio.Event()

        async with (server := await asyncio.start_server(client_callback, self.ifconfig[0], port)):
            await shutdown_event.wait()


    class Response():

        RESPONSE_OK: int = 200
        RESPONSE_NO_CONTENT: int = 204
        RESPONSE_MOVED_PERMANENTLY: int = 301
        RESPONSE_MOVED_TEMPORARY: int = 301
        RESPONSE_TEMPORARY_REDIRECT: int = 307
        RESPONSE_BAD_REQUEST: int = 400
        RESPONSE_UNAUTHORIZED: int = 401
        RESPONSE_FORBIDDEN: int = 403
        RESPONSE_NOT_FOUND: int = 404
        RESPONSE_INTERNAL_SERVER_ERROR: int = 500

        CONTENT_TYPE_HTML: str = 'text/html'
        CONTENT_TYPE_JSON: str = 'application/json'
        CONTENT_TYPE_PLAIN_TEXT: str = 'text/plain'

        def __init__(self) -> None:
            self.url: str = ''
            self.method: str = 'GET'
            self.params: dict = {}
            self.headers: list = []

            self.content: str = ''
            self.content_type: str = 'text/html'
            self.content_headers: dict = {}

        def template(self, template: str, context: dict = {}) -> bool:
            try:
                self.content = ''

                with open(template, 'r') as f:
                    self.content = f.read()

                for name, value in context.items():
                    self.content = self.content.replace(f'[{name}]', value)

                return True
            except Exception as e:
                print(f'RouterHttp.Response.template("{template}"): {e}')
                return False

        def download(self, filename: str) -> bool:
            try:
                self.content = ''
                self.content_type = 'application/octet-stream'
                self.content_headers['Content-disposition'] = f'attachment; filename="{filename.split("/")[-1]}"'
                # self.content_headers['Content-Length'] = os.stat(filename)[6]

                with open(filename, 'r') as f:
                    self.content = f.read()
            
                return True
            except Exception as e:
                print(f'RouterHttp.Response.download("{filename}"): {e}')
                return False

        async def send(self, writer: asyncio.StreamWriter, status_code: int):
            try:
                headers = [f'HTTP/1.1 {status_code}']
                self.content_headers['Content-type'] = self.content_type

                for name, content in self.content_headers.items():
                    headers.append(f'{name}: {content}')
                    
                writer.write(bytes('\r\n'.join(headers) + '\r\n\r\n', 'utf-8'))
                await writer.drain()
                writer.write(bytes(self.content.strip(), 'utf-8'))
                await writer.drain()

                led.value(1)
            except Exception as e:
                print(f'RouterHttp.Response.send("{self.url}"): {e}')
            finally:
                writer.close()
                await writer.wait_closed()
                print(f'{self.method} {self.url} {status_code} {self.content_type} {self.params}')
                led.value(0)
