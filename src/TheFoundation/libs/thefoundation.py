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


class status:

    STATUS_200_OK: int = 200
    STATUS_204_NO_CONTENT: int = 204
    STATUS_307_TEMPORARY_REDIRECT: int = 307
    STATUS_308_PERMANENT_REDIRECT: int = 308
    STATUS_400_BAD_REQUEST: int = 400
    STATUS_401_UNAUTHORIZED: int = 401
    STATUS_403_FORBIDDEN: int = 403
    STATUS_404_NOT_FOUND: int = 404
    STATUS_411_LENGTH_REQUIRED: int = 411
    STATUS_415_UNSUPPORTED_MEDIA_TYPE: int = 415
    STATUS_422_UNPROCESSABLE_ENTITY: int = 422
    STATUS_500_INTERNAL_SERVER_ERROR: int = 500
    STATUS_501_NOT_IMPLEMENTED: int = 501

    STATUS_TEXTS: dict[int, str] = {
        STATUS_200_OK: 'HTTP/1.1 200 OK',
        STATUS_204_NO_CONTENT: 'HTTP/1.1 204 No Content',
        STATUS_307_TEMPORARY_REDIRECT: 'HTTP/1.1 307 Temporary Redirect',
        STATUS_308_PERMANENT_REDIRECT: 'HTTP/1.1 308 Permanent Redirect',
        STATUS_400_BAD_REQUEST: 'HTTP/1.1 400 Bad Request',
        STATUS_401_UNAUTHORIZED: 'HTTP/1.1 401 Unauthorized',
        STATUS_403_FORBIDDEN: 'HTTP/1.1 403 Forbidden',
        STATUS_404_NOT_FOUND: 'HTTP/1.1 404 Not Found',
        STATUS_411_LENGTH_REQUIRED: 'HTTP/1.1 411 Length Required',
        STATUS_415_UNSUPPORTED_MEDIA_TYPE: 'HTTP/1.1 415 Unsupported Media Type',
        STATUS_422_UNPROCESSABLE_ENTITY: 'HTTP/1.1 422 Unprocessable Entity',
        STATUS_500_INTERNAL_SERVER_ERROR: 'HTTP/1.1 500 Internal Server Error',
        STATUS_501_NOT_IMPLEMENTED: 'HTTP/1.1 500 Not Implemented',
    }

    @staticmethod
    def text(status_code: int) -> str:
        return status.STATUS_TEXTS.get(status_code, f'HTTP/1.1 {status_code} Unknown Status Code')
    

class media:

    CONTENT_TYPES: dict[str, str] = {
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

    @staticmethod
    def type(extension: str) -> str:
        return media.CONTENT_TYPES.get(extension.lower(), 'application/octet-stream')


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


class HTTPService:

    def __init__(self):
        self.__items: dict[str, tuple[list[str], callable]] = {}
        self.__static_items: dict[str, str] = {}
    
    def mount(self, path: str, name: str = ''):
        try:
            if (os.stat(path)[0] & 0x4000) != 0:
                self.__static_items[name if name != '' else path] = path
            else:
                raise NotADirectoryError
        except:
            raise Exception(f'"{path}" is not a valid directory!')
        
    def map(self, methods: str, pattern: str, callback: callable) -> callable[[Request], str]:
        self.__items[pattern] = (list(map(lambda s: s.strip(), methods.upper().split('|'))), callback)
        return callback
    
    async def init(self, port: int = 80):
        async def client_callback(reader: asyncio.StreamReader, writer: asyncio.asyncioStreamWriter):
            try:
                gc.collect()
                url: str = ''
                method: str = 'GET'
                headers_sent: dict = {}
                post_data: dict = {}
                query_param: dict = {}

                while True:
                    if (line := (await reader.readline()).decode('utf-8').strip()) == '':
                        break

                    if len(headers_sent) == 0:
                        if (match := re.compile(r'(GET|POST)\s+([^\s]+)\s+HTTP').search(line)):
                            if len(uu := match.group(2).split('?')) == 2:
                                for pp in uu[1].split('&'):
                                    if len(p := pp.split('=')) == 2:
                                        query_param[url_decode(p[0])] = url_decode(p[1])

                            url = uu[0]
                            method = match.group(1)
                    
                    if len(splitted_line := line.split(': ')) == 2:
                        headers_sent[str(splitted_line[0]).lower()] = splitted_line[1]

                if not url:
                    return

                request = HTTPService.Request(url, method, headers_sent, post_data, query_param)

                for name, path in self.__static_items.items():
                    if url.startswith(name):
                        try:
                            if ((stat := os.stat(filename := f'{path}{url[len(name):]}'))[0] & 0x4000) == 0:
                                request.content = open(filename, 'rb').read()
                                request.headers['Content-Type'] = media.type(filename.split('.')[-1])
                                request.headers['Content-Length'] = stat[6]
                                request.status_code = status.STATUS_200_OK

                                return await self.send(writer, request)
                            else:
                                raise FileExistsError
                        except Exception as e:
                            return await self.send(writer, request, status.STATUS_404_NOT_FOUND)
                
                if method == 'POST':            
                    try:
                        if (content_length := int(headers_sent['content-length'])) > 0:
                            stream = await reader.readexactly(content_length)

                            try:
                                content_type = str(headers_sent['content-type']).lower()

                                if 'application/x-www-form-urlencoded' in content_type:
                                    for p in stream.decode('utf-8').split('&'):
                                        k, v = p.split('=')
                                        post_data[url_decode(k)] = url_decode(v)
                                elif 'application/json' in content_type:
                                    post_data = json.loads(stream)
                                else:
                                    raise TypeError
                            except:
                                return await self.send(writer, request, status.STATUS_415_UNSUPPORTED_MEDIA_TYPE)
                    except:
                        return await self.send(writer, request, status.STATUS_411_LENGTH_REQUIRED)

                request = HTTPService.Request(url, method, headers_sent, post_data, query_param)

                for pattern, item in self.__items.items():
                    if request.method not in item[0]:
                        continue

                    if pattern == request.url or (match := re.match('^' + pattern + '$', request.url)):
                        args = []
                        
                        if match:
                            args = [i for i in match.groups() if i is not None]
                        
                        try:
                            request.content = await item[1](request, *args) or ''
                        
                            if request.status_code == 0:
                                request.status_code = status.STATUS_200_OK
                        except:
                            request.status_code = status.STATUS_500_INTERNAL_SERVER_ERROR
                        finally:
                            return await self.send(writer, request)
                    
                return await self.send(writer, request, status.STATUS_404_NOT_FOUND)
            except Exception as e:
                print(f'HTTPService.client_callback(): {e}')
                writer.close()
            
        shutdown_event = asyncio.Event()

        async with await asyncio.start_server(client_callback, wifi.IP, port):
            print(f'$ HTTP service started on: http://{wifi.IP}:{port}')
            await shutdown_event.wait()

    async def send(self, writer: asyncio.StreamWriter, request: 'HTTPService.Request', status_code: int = 0):
        led.value(1)

        try:
            headers = [status.text(status_code or request.status_code)]

            for name, value in request.headers.items():
                headers.append(f'{name}: {value}')
                
            writer.write(bytes('\r\n'.join(headers) + '\r\n\r\n', 'utf-8'))
            await writer.drain()

            if request.content:
                writer.write(bytes(request.content, 'utf-8'))
                await writer.drain()
        except Exception as e:
            print(f'HTTPService.send("{request.url}"): {e}')
        finally:
            writer.close()
            await writer.wait_closed()
            print(f'{serv_crontab.datetime} - {request.method} {status_code or request.status_code} {request.url} ({request.headers.get("Content-Type", "text/html")})')
        
        led.value(0)

    class Request:

        @property
        def url(self) -> str:
            return self.__url
        
        @property
        def method(self) -> str:
            return self.__method
        
        @property
        def headers_sent(self) -> dict:
            return self.__headers_sent
        
        @property
        def post_data(self) -> dict:
            return self.__post_data
        
        @property
        def query_param(self) -> dict:
            return self.__query_param

        def __init__(self, url: str = '', method: str = 'GET', headers_sent: dict = {}, post_data: dict = {}, query_param: dict = {}):
            self.__url: str = url
            self.__method: str = method
            self.__headers_sent: dict = headers_sent
            self.__post_data: dict = post_data
            self.__query_param: dict = query_param

            # Response
            self.content: str|bytes = ''
            self.headers: dict[str, str] = {'Content-Type': 'text/html'}
            self.status_code: int = 0

        def redirect(self, to: str, status_code: int = status.STATUS_307_TEMPORARY_REDIRECT):
            self.content = ''
            self.headers = {'Location': to}

            if status_code not in [status.STATUS_307_TEMPORARY_REDIRECT, status.STATUS_308_PERMANENT_REDIRECT]:
                status_code = status.STATUS_307_TEMPORARY_REDIRECT

            self.status_code = status_code

        def json(self, data: int|str|dict) -> str:
            self.headers['Content-Type'] = 'application/json'

            try:
                self.status_code = status.STATUS_200_OK
                return json.dumps(data)
            except Exception as e:
                self.status_code = status.STATUS_500_INTERNAL_SERVER_ERROR

        def template(self, content: str, context: dict = {}) -> str:
            self.headers['Content-Type'] = 'text/html'
            
            try:
                self.status_code = status.STATUS_200_OK
                return Tf.echo(content, context)
            except Exception as e:
                self.status_code = status.STATUS_500_INTERNAL_SERVER_ERROR
    
        def attachment(self, filename: str) -> bytes:
            try:
                if os.stat(filename)[0] & 0x4000 == 0:
                    self.headers['Content-Type'] = media.type(filename.split('.')[-1]),
                    self.headers['Content-disposition'] = f'attachment; filename="{filename.split("/")[-1]}"'
                    self.status_code = status.STATUS_200_OK

                    return open(filename, 'rb').read()
                else:
                    raise FileNotFoundError
            except Exception as e:
                self.status_code = status.STATUS_500_INTERNAL_SERVER_ERROR


class WebSocketService:

    def __init__(self):
        self.__items: list[tuple[int, int, callable]] = []
        self.websockets: dict[str, list['WebSocketService.WebSocket']] = {}

    def map(self, port: int, max_connections: int, callback: callable) -> callable[['WebSocketService.WebSocket'],]:
        self.__items.append((int(port), int(max_connections), callback))
        return callback

    async def init(self):
        async def client_callback(port: int, max_connections: int, callback: callable):
            self.websockets[(wsid := unique_id())] = []
            
            def on_connect(sock: socket.socket):
                if (websocket := self.handshake(sock, wsid, max_connections)):
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

        return await [client_callback(port=a, max_connections=b, callback=c) for a, b, c in self.__items]

    def handshake(self, sock: socket.socket, wsid: str, max_connections: int = 2) -> 'WebSocketService.WebSocket':
        client, address = sock.accept()

        if max_connections > 0 and len(self.websockets[wsid]) >= max_connections:
            print('Connection refused:', str(address))
            client.setblocking(True)
            client.send(b'HTTP/1.1 429 Too Many Requests\r\n\r\n')
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
            print(f'WebSocket: {e}')
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


class CrontabService:
        
    @property
    def datetime(self) -> str:
        n = time.localtime()
        return f'{n[0]}/{n[1]:0>2}/{n[2]:0>2} {n[3]:0>2}:{n[4]:0>2}:{n[5]:0>2}'
    
    def __init__(self):
        self.__items: list['CrontabService.Schedule'] = []

    def map(self, name: str, callback: callable, month: int|list = -1, date: int|list = -1, hour: int|list = -1, minute: int|list = -1, second: int|list = -1, weekday: int|list = -1) -> callable[[Schedule],]:
        self.__items.append(CrontabService.Schedule(name, callback, month, date, hour, minute, second, weekday))
        return callback

    async def init(self, crontab_interval: int = 1):
        if int(crontab_interval) > 0:
            print(f'$ Crontab service started at: {self.datetime}')

            while True:
                if len(self.__items) > 0:
                    _, month, date, hour, minute, second, weekday, _ = time.localtime()

                    for schedule in self.__items:
                        if schedule.state == True:
                            matched = 0

                            for x, y in [
                                (month, schedule.month), (date, schedule.date), (hour, schedule.hour), 
                                (minute, schedule.minute), (second, schedule.second), (weekday, schedule.weekday),
                            ]:
                                matched += int(y == -1 or x == y or x in list(y))

                            if matched == 6:
                                schedule.n += 1
                                loop = asyncio.get_event_loop()
                                loop.create_task(schedule.callback(schedule))
                        else:
                            self.__items.remove(schedule)

                await asyncio.sleep(crontab_interval)

    class Schedule:

        @property
        def datetime(self) -> str:
            n = time.localtime()
            return f'{n[0]}/{n[1]:0>2}/{n[2]:0>2} {n[3]:0>2}:{n[4]:0>2}:{n[5]:0>2}'

        @property
        def localtime(self) -> tuple:
            return time.localtime()

        def __init__(self, name: str, callback: callable, month: int|list = -1, date: int|list = -1, hour: int|list = -1, minute: int|list = -1, second: int|list = -1, weekday: int|list = -1):
            self.n: int = 0
            self.name: str = name
            self.state: bool = True
            self.callback: callable = callback

            self.month: int|list = month
            self.date: int|list = date
            self.hour: int|list = hour
            self.minute: int|list = minute
            self.second: int|list = second
            self.weekday: int|list = weekday
            self.__check_values()

        def next(self, month: int|list = -1, date: int|list = -1, hour: int|list = -1, minute: int|list = -1, second: int|list = -1, weekday: int|list = -1):
            self.state = True

            self.month = month
            self.date = date
            self.hour = hour
            self.minute = minute
            self.second = second
            self.weekday = weekday
            self.__check_values()
        
        def stop(self):
            self.state = False

        def __check_values(self):
            for attribute, accept_values in [
                ('month', range(1, 13)), ('date', range(1, 32)), ('weekday', range(0, 7)),
                ('hour', range(0, 24)), ('minute', range(0, 60)), ('second', range(0, 60)),
            ]:
                if (value := getattr(self, attribute)) == -1:
                    continue
                
                for v in list(value):
                    if v not in accept_values:
                        raise ValueError(f'Schedule.{attribute}\'s value <{v}> is out of bound <{accept_values[0]} - {accept_values[-1]}>')


led = machine.Pin('LED', machine.Pin.OUT)
wifi: WiFi = WiFi()
serv_http: HTTPService = HTTPService()
serv_crontab: CrontabService = CrontabService()
serv_websocket: WebSocketService = WebSocketService()


class Request(HTTPService.Request):
    pass


class WebSocket(WebSocketService.WebSocket):
    pass


class WebSocketDisconnect(WebSocket.WebSocketDisconnect):
    pass


class Schedule(CrontabService.Schedule):
    pass


class TheFoundation:

    @property
    def wifi(self) -> WiFi:
        return wifi
    
    def connect(self, ssid: str, password: str, timezone: int = 0) -> bool:
        return wifi.connect(ssid, password, timezone)
    
    def mount(self, path: str, name: str = ''):
        serv_http.mount(path, name)

    def map(self, methods: str, pattern: str) -> callable[[Request], str]:
        def decorator(callback: callable):
            return serv_http.map(methods, pattern, callback)

        return decorator

    def websocket(self, port: int, max_connections: int = 2) -> callable[[WebSocket],]:
        def decorator(callback: callable):
            return serv_websocket.map(port, max_connections, callback)

        return decorator

    def schedule(self, month: int = -1, date: int = -1, hour: int = -1, minute: int = -1, second: int = -1, weekday: int = -1, name: str = '') -> callable[[Schedule],]:
        def decorator(callback: callable):
            return serv_crontab.map(name or unique_id(), callback, month, date, hour, minute, second, weekday)
        
        return decorator
    
    def add_background_task(self, callback: callable, kwargs: dict = {}):
        loop = asyncio.get_event_loop()
        loop.create_task(callback(**kwargs))

    def listen(self, port: int = 80, crontab_interval: int = 1):
        async def serve_forever():
            await asyncio.gather(serv_http.init(port), serv_crontab.init(crontab_interval), *serv_websocket.init())
        
        asyncio.run(serve_forever())
