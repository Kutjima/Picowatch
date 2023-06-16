import gc
import os
import re
import json
import time
import socket
import machine
import network
import ntptime
import uhashlib as hashlib
import uasyncio as asyncio
import ubinascii as binascii

from websocket import websocket as base_websocket


led = machine.Pin('LED', machine.Pin.OUT)


def url_decode(encoded: str) -> str:
    i = 0
    decoded: str = ''
    encoded = encoded.replace('+', ' ')

    while i < len(encoded):
        if encoded[i] == '%':
            decoded += chr(int(encoded[i + 1:i + 3], 16))
            i += 3
        else:
            decoded += encoded[i]
            i += 1

    return decoded
    

def unique_id(length: int = 8, seeds: str = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') -> str:
    return ''.join([seeds[x] for x in [(os.urandom(1)[0] % len(seeds)) for _ in range(0, length)]])


class Tz:

    def __init__(self, data: dict = {}):
        for k, v in data.items():
            if isinstance(v, dict):
                v = Tz(v)
            elif isinstance(v, list):
                for i, vv in enumerate(v):
                    v[i] = Tz(vv) if isinstance(vv, dict) else vv
                        
            setattr(self, k, v)

    def __getitem__(self, k: str) -> any:
        return getattr(self, k)
    
    def __str__(self) -> str:
        return str(self.__dict__)
    
    def __len__(self) -> int:
        return len(self.__dict__)
    
    def items(self) -> dict[str, any]:
        return self.__dict__.items()
    

class Tf:

    @staticmethod
    def set(name: str, content: str) -> str:
        content = str(content).replace('"', '\\"')

        return exec(f'{name} = "{content}"') or ''

    @staticmethod
    def echo(content: str, context: dict = {}, times: iter = [0]) -> str:
        global k, v, i, item

        if (content := str(content)) and (content.endswith('.html') or content.endswith('.tpl')):
            with open(content, 'r') as f:
                content = f.read()
        elif content.endswith('.py'):
            with open(content, 'r') as f:
                return exec(f.read()) or ''
        
        for k, v in context.items():
            if not isinstance(v, dict):
                exec(f'{k} = v')
            else:
                exec(f'{k} = Tz(v)') 

            del k, v

        if isinstance(times, (Tz, dict)):
            times = times.items()
        elif isinstance(times, list):
            times = enumerate(times)
        else:
            raise TypeError('times must be iterable')
        
        echo = ''

        for i, item in times:
            try:
                if not isinstance(item, dict):
                    item = item
                else:
                    item = Tz(item)

                # , r'\{\s*(.*?)\s*\}'
                for pattern in [r'\<\?\=\s*(.*?)\s*\?\>']:
                    content = re.sub(pattern, lambda match: str(eval(match.group(1) or '')), content)

                echo += content
            except Exception as e:
                raise e

        return echo

    @staticmethod
    def match(expression: str, then: str|dict):
        return Tf.Statement().match(expression, then)

    class Statement:

        def __init__(self):
            self.content: str = False

        def match(self, expression: str, then: str|dict):
            if not isinstance(then, (str, dict)):
                raise TypeError('then must be str or dict')

            global k, v

            if self.content == False and eval(str(expression)):
                if isinstance(then, dict):
                    self.content = ''

                    for k, v in then.items():
                        if not isinstance(v, dict):
                            exec(f'{k} = v')
                        else:
                            exec(f'{k} = Tz(v)') 

                        del k, v
                else:
                    self.content = str(then)

            return self
        
        def nomatch(self, then: str|dict = '') -> str:
            if not isinstance(then, (str, dict)):
                raise TypeError('then must be str or dict')

            global k, v

            if self.content == False:
                if isinstance(then, dict):
                    self.content = ''

                    for k, v in then.items():
                        if not isinstance(v, dict):
                            exec(f'{k} = v')
                        else:
                            exec(f'{k} = Tz(v)') 

                        del k, v
                else:
                    self.content = str(then)

            return Tf.echo(self.content)


class HTTP:

    STATUS_OK: int = 200
    STATUS_NO_CONTENT: int = 204
    STATUS_MOVED_PERMANENTLY: int = 301
    STATUS_MOVED_TEMPORARY: int = 302
    STATUS_TEMPORARY_REDIRECT: int = 307
    STATUS_BAD_REQUEST: int = 400
    STATUS_UNAUTHORIZED: int = 401
    STATUS_FORBIDDEN: int = 403
    STATUS_NOT_FOUND: int = 404
    STATUS_LENGTH_REQUIRED: int = 411
    STATUS_UNSUPPORTED_MEDIA_TYPE: int = 415
    STATUS_UNPROCESSABLE_ENTITY: int = 422
    STATUS_INTERNAL_SERVER_ERROR: int = 500

    HEADER_CONTENT_TYPE: dict = {
        'html': 'text/html',
        'css': 'text/css',
        'js': 'application/javascript',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp',
        'ico': 'image/x-icon',
        'svg': 'image/svg+xml',
        'json': 'application/json',
        'xml': 'application/xml',
        'pdf': 'application/pdf',
        'zip': 'application/zip',
        'txt': 'text/plain',
        'csv': 'text/csv',
        'mp3': 'audio/mpeg',
        'mp4': 'video/mp4',
        'wav': 'audio/wav',
        'ogg': 'audio/ogg',
        'webm': 'video/webm',
    }

    def __init__(self):
        gc.collect()
        self.request = self.Request()
        self.response = self.Response()

    def add_background_task(self, callback: callable, kwargs: dict = {}):
        loop = asyncio.get_event_loop()
        loop.create_task(callback(**kwargs))

    class Request:

        def __init__(self):
            self.url: str = ''
            self.method: str = 'GET'
            self.params: dict = {}
            self.headers: dict = {}
            self.post_data: dict = {}

        def redirect_to(self, url: str):
            raise NotImplementedError()
        
    class Response:

        def __init__(self):
            self.content: str = ''
            self.content_type: str = 'text/html'
            self.content_headers: dict = {}

        def template(self, content: str, context: dict = {}) -> tuple[int, str]:
            try:
                return (HTTP.STATUS_OK, Tf.echo(content, context))
            except Exception as e:
                return (HTTP.STATUS_INTERNAL_SERVER_ERROR, f'Response.template("{content}"): {e}')
    
        def attachment(self, filename: str) -> int:
            try:
                if os.stat(filename)[0] & 0x4000 == 0:
                    with open(filename, 'rb') as f:
                        self.content = f.read()
                        self.content_type = HTTP.HEADER_CONTENT_TYPE.get(filename.lower().split('.')[-1], 'application/octet-stream')
                        self.content_headers['Content-disposition'] = f'attachment; filename="{filename.split("/")[-1]}"'
                    
                    return HTTP.STATUS_OK
                else:
                    raise FileNotFoundError()
            except Exception as e:
                print(f'RouterHTTP.Response.attachment("{filename}"): {e}')
            
            return HTTP.STATUS_NOT_FOUND


class WebSocketService:

    def __init__(self):
        self.websockets: dict[str, list['WebSocketService.WebSocket']] = {}

    async def init(self, port: int, max_tasks: int, callback: callable):
        self.websockets[(wsid := unique_id())] = []
        
        def on_connect(sock: socket.socket):
            if (websocket := self.handshake(sock, wsid, max_tasks)):
                loop = asyncio.get_event_loop()
                loop.create_task(callback(websocket))

                if websocket not in self.websockets[wsid]:
                    self.websockets[wsid].append(websocket)
    
        sock: socket.socket = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', port))
        sock.listen(1)
        sock.setsockopt(socket.SOL_SOCKET, 20, on_connect)

        for i in [network.STA_IF, network.AP_IF]:
            if network.WLAN(i).active():
                print(f'$ WebSocket service started on ws://{wifi.IP}:{port}')
                break
        else:
            raise Exception(f'$ Unable to start WebSocket service on ws://{wifi.IP}:{port}')

        while True:
            for websocket in self.websockets[wsid]:
                if websocket.is_closed:
                    self.websockets[wsid].remove(websocket)
            
            await asyncio.sleep(1)

    def handshake(self, sock: socket.socket, wsid: str, max_tasks: int = 2) -> 'WebSocketService.WebSocket':
        client, address = sock.accept()

        if max_tasks > 0 and len(self.websockets[wsid]) >= max_tasks:
            print('Connection refused:', str(address))
            client.setblocking(True)
            client.send(b'HTTP/1.1 503 Too many connections\r\n')
            client.send(b'\r\n\r\n')
            time.sleep(0.1)
            return client.close()

        try:
            websocket = WebSocketService.WebSocket(wsid, client, address)
            stream = client.makefile('rwb', 0)
            time.sleep(0.25)
            line = stream.readline()

            while True:
                if not (line := stream.readline()) or line == b'\r\n':
                    break

                h, v = [x.strip().decode() for x in line.split(b':', 1)]
                websocket.headers[h] = v

            if not websocket.token:
                raise Exception(f'"Sec-WebSocket-Key" not found in client<{address}>\'s headers!')
            
            headers = [
                'HTTP/1.1 101 Switching Protocols', 
                'Upgrade: websocket', 
                'Connection: Upgrade', 
                f'Sec-WebSocket-Accept: {websocket.token_digest}'
            ]
            
            client.send(bytes('\r\n'.join(headers) + '\r\n\r\n', 'utf-8'))
            print('Connection accepted:', str(websocket.address))

            return websocket
        except Exception as e:
            print(f'WebSocket Exception: {e}')
            return client.close()

    class WebSocket:

        @property
        def token(self) -> str:
            return self.headers.get('Sec-WebSocket-Key', '')

        @property
        def token_digest(self) -> str:
            d = hashlib.sha1(self.token)
            d.update('258EAFA5-E914-47DA-95CA-C5AB0DC85B11')
            
            return (binascii.b2a_base64(d.digest())[:-1]).decode()
        
        @property
        def websockets(self) -> list['WebSocketService.WebSocket']:
            return serv_websocket.websockets[self.__wsid]

        @property
        def is_opened(self) -> bool:
            return self.__socket is not None
        
        @property
        def is_closed(self) -> bool:
            return self.__socket is None
        
        @property
        def socket_state(self) -> int:
            if self.is_closed:
                return 4

            return int((str(self.__socket).split(' ')[1]).split('=')[1])
        
        def __init__(self, wsid: str, client: socket.socket, address: tuple[str, int]):
            self.address = address
            self.headers: dict[str, str] = {}

            self.__wsid = wsid
            self.__socket: socket.socket = client
            self.__websocket: base_websocket = base_websocket(self.__socket, True)
            self.__socket.setblocking(False)
            self.__socket.setsockopt(socket.SOL_SOCKET, 20, self.__heartbeat)

        def __heartbeat(self, _):
            if self.socket_state == 4:
                self.close()

        def close(self):
            if self.__socket is not None:
                print('Connection closed:', str(self.address))
                self.__socket.setsockopt(socket.SOL_SOCKET, 20, None)
                self.__socket.close()
                self.__socket = self.__websocket = None

                for websocket in self.websockets:
                    if self is websocket:
                        self.websockets.remove(websocket)

        async def recv(self, decode_to: str = 'utf-8'):
            if self.socket_state == 4:
                self.close()

            while self.__websocket:
                if (message := self.__websocket.read()):
                    if decode_to:
                        return message.decode(decode_to)

                    return message
                
                await asyncio.sleep(0)
            
            raise WebSocketService.WebSocket.WebSocketDisconnect

        def send(self, message: str):
            if self.socket_state == 4:
                self.close()

            if self.is_closed:
                raise WebSocketService.WebSocket.WebSocketDisconnect

            self.__websocket.write(message)

        def broadcast(self, message: str):
            for websocket in self.websockets:
                try:
                    websocket.send(message)
                except:
                    pass
        
        class WebSocketDisconnect(Exception):

            def __init__(self, code: int = 1000, reason: str = ''):
                self.code = code
                self.reason = reason


class WebSocket(WebSocketService.WebSocket):
    pass


class WebSocketDisconnect(WebSocketService.WebSocket.WebSocketDisconnect):
    pass


class CrontabService:
        
    @property
    def datetime(self) -> str:
        n = time.localtime()
        return f'{n[0]}/{n[1]:0>2}/{n[2]:0>2} {n[3]:0>2}:{n[4]:0>2}:{n[5]:0>2}'
    
    def __init__(self):
        self.schedules: list['CrontabService.Schedule'] = []

    async def init(self, crontab_interval: int = 1):
        print(f'$ Crontab service started at: {self.datetime}')

        while True:
            if len(self.schedules) > 0:
                _, month, date, hour, minute, second, weekday, _ = time.localtime()

                for schedule in self.schedules:
                    if schedule.state == True:
                        matched = 0

                        for x, y in [
                            (month, schedule.month), (date, schedule.date), (hour, schedule.hour), 
                            (minute, schedule.minute), (second, schedule.second), (weekday, schedule.weekday),
                        ]:
                            matched += int(y == -1 or x == y)

                        if matched == 6:
                            loop = asyncio.get_event_loop()
                            loop.create_task(schedule.callback(schedule))
                    else:
                        self.schedules.remove(schedule)

            await asyncio.sleep(crontab_interval)

    class Schedule:

        @property
        def datetime(self) -> str:
            n = time.localtime()
            return f'{n[0]}/{n[1]:0>2}/{n[2]:0>2} {n[3]:0>2}:{n[4]:0>2}:{n[5]:0>2}'

        @property
        def localtime(self) -> tuple:
            return time.localtime()

        def __init__(self, name: str, callback: callable, month: int = -1, date: int = -1, hour: int = -1, minute: int = -1, second: int = -1, weekday: int = -1):
            self.name: str = name
            self.state: bool = True
            self.callback: callable = callback

            self.month: int = int(month)
            self.date: int = int(date)
            self.hour: int = int(hour)
            self.minute: int = int(minute)
            self.second: int = int(second)
            self.weekday: int = int(weekday)

        def next(self, month: int = -1, date: int = -1, hour: int = -1, minute: int = -1, second: int = -1, weekday: int = -1):
            self.state: bool = True

            self.month: int = int(month)
            self.date: int = int(date)
            self.hour: int = int(hour)
            self.minute: int = int(minute)
            self.second: int = int(second)
            self.weekday: int = int(weekday)
        
        def stop(self):
            self.state = False


class Schedule(CrontabService.Schedule):
    pass


class WiFi:
    
    @property
    def is_connected(self) -> bool:
        return self.__wlan.isconnected()
    
    @property
    def IP(self) -> str:
        return self.__wlan.ifconfig()[0]
    
    def __init__(self):
        self.__wlan: network.WLAN = network.WLAN(network.STA_IF)
        self.__wlan.active(False)

    def connect(self, ssid: str, password: str, timezone: int = 0) -> bool:
        self.__wlan.active(True)
        self.__wlan.connect(ssid, password)
        time.sleep(1)

        for _ in range(0, 2):
            if self.__wlan.status() < 0 or self.__wlan.status() >= 3:
                break

            time.sleep(4)

        if self.__wlan.isconnected():
            time.gmtime(ntptime.time() + (timezone * 3600))
            print(f'$ Connection succeeded to WiFi: {ssid}')

        return self.__wlan.isconnected()

wifi = WiFi()
serv_crontab: CrontabService = CrontabService()
serv_websocket: WebSocketService = WebSocketService()


class RouterHTTP:

    @property
    def is_connected(self) -> bool:
        return wifi.is_connected

    def __init__(self):
        self.__https: dict[str, callable] = {}
        self.__statics: dict[str, callable] = {}
        self.__websockets: list = []
    
    def setup(self, ssid: str, password: str, timezone: int = 0) -> bool:
        return wifi.connect(ssid, password, timezone)

    def mount(self, path: str, name: str = ''):
        try:
            if (os.stat(path)[0] & 0x4000) != 0:
                self.__statics[name if name != '' else path] = path
            else:
                raise NotADirectoryError()
        except:
            raise Exception(f'"{path}" is not a valid directory!')
    
    def http(self, methods: str|int, pattern: str = ''):
        def decorator(callback: callable) -> callable[[HTTP], int]:
            self.__https[pattern] = (list(map(lambda s: s.strip(), methods.upper().split('|'))), callback)

        return decorator

    def websocket(self, port: int, max_tasks: int = 2):
        def decorator(callback: callable) -> callable[[WebSocket],]:
            self.__websockets.append((int(port), max_tasks, callback))

        return decorator

    def schedule(self, month: int = -1, date: int = -1, hour: int = -1, minute: int = -1, second: int = -1, weekday: int = -1, name: str = ''):
        def decorator(callback: callable) -> callable[[str, tuple],]:
            serv_crontab.schedules.append(CrontabService.Schedule(name or unique_id(), callback, month, date, hour, minute, second, weekday))
        
        return decorator
    
    async def init(self, port: int = 80):
        async def client_callback(reader: asyncio.StreamReader, writer: asyncio.asyncioStreamWriter):
            try:
                http = HTTP()

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
                        return await self.__send(writer, http, HTTP.STATUS_LENGTH_REQUIRED)

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
                        return await self.__send(writer, http, HTTP.STATUS_UNSUPPORTED_MEDIA_TYPE)
                elif http.request.method == 'GET':
                    for name, path in self.__statics.items():
                        if http.request.url.startswith(name):
                            try:
                                if ((stat := os.stat(filename := f'{path}{http.request.url[len(name):]}'))[0] & 0x4000) == 0:
                                    with open(filename, 'rb') as fh:
                                        http.response.content = fh.read()
                                        http.response.content_type = HTTP.HEADER_CONTENT_TYPE.get(filename.lower().split('.')[-1], 'application/octet-stream')
                                        http.response.content_headers['Content-Length'] = stat[6]
                                        
                                    return await self.__send(writer, http, HTTP.STATUS_OK)
                                else:
                                    raise FileNotFoundError()
                            except:
                                return await self.__send(writer, http, HTTP.STATUS_NOT_FOUND)

                for pattern, item in self.__https.items():
                    if http.request.method not in item[0]:
                        continue

                    if pattern == http.request.url or (match := re.match('^' + pattern + '$', http.request.url)):
                        args = []
                        
                        if match:
                            args = [i for i in match.groups() if i is not None]

                        return await self.__send(writer, http, await item[1](http, *args) or HTTP.STATUS_OK)
                    
                return await self.__send(writer, http, HTTP.STATUS_NOT_FOUND)
            except OSError as e:
                print(f'RouterHTTP.client_callback(): {e}')
                writer.close()
            
        shutdown_event = asyncio.Event()

        async with (_ := await asyncio.start_server(client_callback, wifi.IP, port)):
            print(f'$ RouterHTTP service started on: http://{wifi.IP}:{port}')
            await shutdown_event.wait()

    async def __send(self, writer: asyncio.StreamWriter, http: HTTP, status_code: int):
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
            print(f'RouterHTTP.__send("{http.request.url}"): {e}')
        finally:
            writer.close()
            await writer.wait_closed()
            print(f'{serv_crontab.datetime} - {http.request.method} {status_code} {http.request.url} ({http.response.content_type})')
        
        led.value(0)
        
    def listen(self, port: int = 80, crontab_interval: int = 1):
        async def serve_forever():
            await asyncio.gather(
                self.init(port),
                serv_crontab.init(crontab_interval),
                *[serv_websocket.init(port, max_tasks, callback) for port, max_tasks, callback in self.__websockets]
            )
        
        asyncio.run(serve_forever())
