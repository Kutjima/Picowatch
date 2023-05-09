import gc
import re
import json
import time
import machine
import network
import uasyncio as asyncio


led = machine.Pin('LED', machine.Pin.OUT)


def url_decode(encoded: str):
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
    

class HTTP():

    STATUS_OK: int = 200
    STATUS_NO_CONTENT: int = 204
    STATUS_MOVED_PERMANENTLY: int = 301
    STATUS_MOVED_TEMPORARY: int = 301
    STATUS_TEMPORARY_REDIRECT: int = 307
    STATUS_BAD_REQUEST: int = 400
    STATUS_UNAUTHORIZED: int = 401
    STATUS_FORBIDDEN: int = 403
    STATUS_NOT_FOUND: int = 404
    STATUS_LENGTH_REQUIRED: int = 411
    STATUS_UNSUPPORTED_MEDIA_TYPE: int = 415
    STATUS_UNPROCESSABLE_ENTITY: int = 422
    STATUS_INTERNAL_SERVER_ERROR: int = 500

    def __init__(self):
        self.request = self.Request()
        self.response = self.Response()
    
    class Request():

        def __init__(self):
            self.url: str = ''
            self.method: str = 'GET'
            self.params: dict = {}
            self.headers: dict = {}
            self.post_data: dict = {}

    class Response():

        def __init__(self):
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
                print(f'RouterHTTP.Response.template("{template}"): {e}')
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
                print(f'RouterHTTP.Response.download("{filename}"): {e}')
                return False


class RouterHTTP():

    def __init__(self, ssid: str, password: str):
        self.patterns  = {}
        self.status_codes = {}

        self.wlan = network.WLAN(network.STA_IF)
        # activate the interface
        self.wlan.active(True)
        # connect to the access point with the ssid and password
        self.wlan.connect(ssid, password)

        for c in range(0, 10):
            time.sleep(1)

            if self.wlan.status() < 0 or self.wlan.status() >= 3:
                break

        if self.wlan.isconnected() == False:
            raise RuntimeError('Connection failed to WiFi')
        else:
            self.ifconfig = self.wlan.ifconfig()
            print(s := f'Connection succeeded to WiFi = {ssid} with IP = {self.ifconfig[0]}')
            print('-' * len(s))

    def listen(self, port: int = 80):
        asyncio.run(self.start_server(port))

    def listen_with_background_task(self, background_task: callable, port: int = 80):
        if not callable(background_task):
            raise TypeError('background_task must be callable')
        
        async def serve_forever():
            await asyncio.gather(self.start_server(port), background_task())
        
        asyncio.run(serve_forever())

    def map(self, methods: str|int, pattern: str = ''):
        def decorator(callback: callable) -> callable[[HTTP], int]:
            if str(methods).isdigit():
                self.status_codes[int(methods)] = callback
            else:
                self.patterns[pattern] = (list(map(lambda s: s.strip(), methods.upper().split('|'))), callback)
            
            return callback
        return decorator

    async def start_server(self, port: int = 80):        
        async def client_callback(reader: asyncio.StreamReader, writer: asyncio.asyncioStreamWriter):
            gc.collect()

            try:
                http = HTTP()
                status_code = HTTP.STATUS_NOT_FOUND

                while True:
                    if (line := (await reader.readline()).decode('utf-8').strip()) == '':
                        break

                    if len(http.request.headers) == 0:
                        if (match := re.compile(r'(GET|POST)\s+([^\s]+)\s+HTTP').search(line)):
                            if len(uu := match.group(2).split('?')) == 2:
                                for pp in uu[1].split('&'):
                                    if len(p := pp.split('=')) == 2:
                                        http.request.params[url_decode(p[0])] = url_decode(p[1])

                            http.request.url = uu[0]
                            http.request.method = match.group(1)
                    
                    if len(splitted_line := line.split(': ')) == 2:
                        http.request.headers[str(splitted_line[0]).lower()] = splitted_line[1]

                if not http.request.url:
                    return
                
                if http.request.method == 'POST':            
                    try:
                        if (content_length := int(http.request.headers['content-length'])) > 0:
                            post_data = await reader.readexactly(content_length)
                    except:
                        return await self.send(writer, http, HTTP.STATUS_LENGTH_REQUIRED)

                    try:
                        content_type = str(http.request.headers['content-type']).lower()

                        if 'application/x-www-form-urlencoded' in content_type:
                            for p in post_data.decode('utf-8').split('&'):
                                k, v = p.split('=')
                                http.request.post_data[url_decode(k)] = url_decode(v)
                        elif 'application/json' in content_type:
                            http.request.post_data = json.loads(post_data)
                        else:
                            raise TypeError()
                    except:
                        return await self.send(writer, http, HTTP.STATUS_UNSUPPORTED_MEDIA_TYPE)

                for pattern, item in self.patterns.items():
                    if http.request.method not in item[0]:
                        continue

                    if pattern == http.request.url or (match := re.match('^' + pattern + '$', http.request.url)):
                        status_code = item[1](http, *[i for i in match.groups() if i is not None]) or HTTP.STATUS_NO_CONTENT

                if status_code in self.status_codes:
                    self.status_codes[status_code](http)

                return await self.send(writer, http, status_code)
            except OSError as e:
                print(f'RouterHTTP.client_callback(): {e}')
                writer.close()
            
        shutdown_event = asyncio.Event()

        async with (server := await asyncio.start_server(client_callback, self.ifconfig[0], port)):
            await shutdown_event.wait()

    async def send(self, writer: asyncio.StreamWriter, http: HTTP, status_code: int):
        led.value(1)

        try:
            headers = [f'HTTP/1.1 {status_code}']
            http.response.content_headers['Content-type'] = http.response.content_type

            for name, content in http.response.content_headers.items():
                headers.append(f'{name}: {content}')
                
            writer.write(bytes('\r\n'.join(headers) + '\r\n\r\n', 'utf-8'))
            await writer.drain()
            writer.write(bytes(http.response.content, 'utf-8'))
            await writer.drain()
        except Exception as e:
            print(f'RouterHTTP.send("{http.request.url}"): {e}')
        finally:
            writer.close()
            await writer.wait_closed()
        
        led.value(0)
