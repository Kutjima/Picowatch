import gc
import os
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
    def eval(match: re.match):
        try:
            return str(eval(match.group(1)) or '') 
        except Exception as e:
            raise Exception(f'Tf.eval(tag={str(match.group(0)).replace("<", "&lt;")}): {str(e)}')

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

                echo += re.sub(r'\{\s*(.*?)\s*\}', Tf.eval, re.sub(r'\<\?\=\s*(.*?)\s*\?\>', Tf.eval, content))
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
        self.request = self.Request()
        self.response = self.Response()
    
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

        def template(self, content: str, context: dict = {}) -> str|bool:
            try:
                return Tf.echo(content, context)
            except Exception as e:
                return f'Response.template("{content}"): {e}'
    
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


class RouterHTTP:

    def __init__(self, ssid: str, password: str, ignore_exception: bool = False):
        self.mounts = {}
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
            if not ignore_exception:
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
            if str(methods).isdigit() and methods not in [200, 204, 301, 302, 307]:
                self.status_codes[int(methods)] = callback
            else:
                self.patterns[pattern] = (list(map(lambda s: s.strip(), methods.upper().split('|'))), callback)
            
            return callback
        return decorator
    
    def mount(self, path: str, name: str = ''):
        try:
            if (os.stat(path)[0] & 0x4000) != 0:
                self.mounts[name if name != '' else path] = path
            else:
                raise NotADirectoryError()
        except:
            raise Exception(f'"{path}" is not a valid directory!')

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
                elif http.request.method == 'GET':
                    for name, path in self.mounts.items():
                        if http.request.url.startswith(name):
                            try:
                                if ((stat := os.stat(filename := f'{path}{http.request.url[len(name):]}'))[0] & 0x4000) == 0:
                                    with open(filename, 'rb') as fh:
                                        http.response.content = fh.read()
                                        http.response.content_type = HTTP.HEADER_CONTENT_TYPE.get(filename.lower().split('.')[-1], 'application/octet-stream')
                                        http.response.content_headers['Content-Length'] = stat[6]
                                        status_code = HTTP.STATUS_OK
                                else:
                                    raise FileNotFoundError()
                            except:
                                status_code = HTTP.STATUS_NOT_FOUND

                                if status_code in self.status_codes:
                                    self.status_codes[status_code](http)

                            return await self.send(writer, http, status_code)

                for pattern, item in self.patterns.items():
                    if http.request.method not in item[0]:
                        continue

                    if pattern == http.request.url or (match := re.match('^' + pattern + '$', http.request.url)):
                        args = []
                        
                        if match:
                            args = [i for i in match.groups() if i is not None]

                        status_code = item[1](http, *args) or HTTP.STATUS_NO_CONTENT

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
            n = time.localtime()
            
            print(f'{n[0]}/{n[1]:0>2}/{n[2]:0>2} {n[3]:0>2}:{n[4]:0>2}:{n[5]:0>2} - {http.request.method} {status_code} {http.request.url} ({http.response.content_type})')
        
        led.value(0)
