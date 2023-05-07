#!/usr/bin/env python

import os
import sys
import time
import json
import signal
import tempfile
import binascii
import textwrap
import mpy_cross
import subprocess

try:
    import readline
except:
    pass

from serial import Serial
from dotenv import dotenv_values
from typing import List, Optional, Tuple, Union


BUFFER_SIZE: int = 512
LISTENING_TO: str = os.getcwd()


class Tab():
    bordered: bool = False
    colsize: List = []
    text_to_right: List = []

    def __init__(self, *colsizes: int, align_to_right: Union[List, Tuple] = [], nb_columns: int = 0, bordered: bool = False):
        self.colsize = list(colsizes)
        self.bordered = bordered
        auto_size = nb_columns - len(self.colsize)

        if nb_columns > 0 and auto_size > 0:
            terminal_size = os.get_terminal_size()
            column_size = int((terminal_size.columns - sum(self.colsize) - 1) / auto_size)

            for i in range(len(self.colsize), nb_columns):
                self.colsize.append(column_size)

        if isinstance(align_to_right, (list, tuple)):
            self.align_to_right(*align_to_right)

    def head(self, *labels: str, border_style: str = '='):
        self.border(border_style)
        self.line(*labels, bordered=False)
        self.border(border_style)

    def border(self, style: str = '-'):
        print(style * sum(self.colsize) + '\r')

    def align_to_right(self, *column_num: int):
        self.text_to_right = [i - 1 for i in column_num]

    def line(self, *texts: str, bordered: bool = None, border_style: str = '-'):
        lines = {}
        max_lines = 0

        for column_num, text in enumerate(texts[:len(self.colsize)]):
            max_length = self.colsize[column_num]
            lineno = -1
            lines[column_num] = (max_length, [])

            for paragraph in str(text).split('\n'):
                lineno += 1
                lines[column_num][1].append([])

                for word in paragraph.split(' '):
                    word = word.strip()
                    next_sentence = ' '.join(lines[column_num][1][lineno] + [word])

                    if len(next_sentence) > max_length:
                        lineno += 1
                        lines[column_num][1].append([])

                    lines[column_num][1][lineno].append(word)
                    
            max_lines = max(max_lines, lineno)

        for i in range(0, max_lines + 1):
            output = ''

            for column_num, line in lines.items():
                width, bag_of_words = line

                if len(bag_of_words) > i:
                    sentence = ' '.join(bag_of_words[i])

                    if column_num in self.text_to_right:
                        output += ' ' * (width - len(sentence) - 1) + sentence + ' '
                    else:
                        output += sentence + ' ' * (width - len(sentence))
                else:
                    output += ' ' * width

            print(output + '\r')
        
        if bordered == False:
            return

        if bordered or self.bordered:
            self.border(border_style)


class Telnet:

    def __init__(self, IP: str, login: str, password: str):
        import telnetlib
        from collections import deque

        self.tn = telnetlib.Telnet(IP, timeout=15)
        self.fifo = deque()

        if b'Login as:' in self.tn.read_until(b'Login as:'):
            self.tn.write(bytes(login, 'ascii') + b'\r\n')

            if b'Password:' in self.tn.read_until(b'Password:'):
                time.sleep(0.2)
                self.tn.write(bytes(password, 'ascii') + b'\r\n')

                if b'for more information.' in self.tn.read_until(b'Type "help()" for more information.'):
                    return

        raise Exception('Failed to establish a Telnet connection with the board')

    def __del__(self):
        self.close()

    def close(self):
        try:
            self.tn.close()
        except:
            pass

    def read(self, size: int = 1) -> bytes:
        timeout = 0

        while len(self.fifo) < size and not timeout >= 8:
            timeout = 0
            data = self.tn.read_eager()

            if len(data):
                self.fifo.extend(data)
                timeout = 0
            else:
                timeout += 1
                time.sleep(0.25)

        data = b''

        while len(data) < size and len(self.fifo) > 0:
            data += bytes([self.fifo.popleft()])

        return data

    def write(self, data: bytes):
        self.tn.write(data)
        return len(data)

    def inWaiting(self) -> int:
        n_waiting = len(self.fifo)

        if not n_waiting:
            data = self.tn.read_eager()
            self.fifo.extend(data)
            n_waiting = len(data)
        
        return n_waiting


class Pyboard(object):
    i: int = 0
    boot_status: bool = False
    serial: Union[Serial, Telnet]

    def __init__(self, device: str, baudrate: int = 115200, login: str = 'micro', password: str = 'python'):
        is_telnet = device and device.count('.') == 3

        for _ in range(0, 3):
            try:
                if is_telnet:
                    self.serial = Telnet(device, login, password)
                else:
                    self.serial = Serial(device, baudrate=baudrate, interCharTimeout=1)
                break
            except:
                time.sleep(1)
        else:
            raise Exception(f'Failed to access device: {device}')

    def close(self):
        self.serial.close()

    def transfer_status(self) -> int:
        arrows = ['◜', '◝', '◞', '◟']
        sys.stdout.write(f'[∘] Transfering... {arrows[self.i]}\r')
        sys.stdout.flush()
        self.i = (self.i + 1) % 4      

    def send_ok(self) -> bytes:
        self.serial.write(b'\x04')
        return b'OK'

    def send_ctrl_a(self) -> bytes:
        # Ctrl-A on a blank line will enter raw REPL mode. This is like a permanent paste mode, except that characters are not echoed back.
        self.serial.write(b'\x01')
        return b'raw REPL; CTRL-B to exit\r\n>'

    def send_ctrl_b(self):
        # Ctrl-B on a blank like goes to normal REPL mode.
        self.serial.write(b'\x02')

    def send_ctrl_c(self) -> bytes:
        self.boot_status = False
        # Ctrl-C cancels any input, or interrupts the currently running code.
        for _ in range(0, 2):
            self.serial.write(b'\x03')

        return b'raw REPL; CTRL-B to exit\r\n'

    def send_ctrl_d(self) -> bytes:
        # Ctrl-D on a blank line will do a soft reset.
        self.serial.write(b'\x04')
        return b'soft reboot\r\n'

    def until_nothing_in_waiting(self):
        n = self.serial.inWaiting()

        while n > 0:
            self.serial.read(n)
            n = self.serial.inWaiting()        

    def read_until(self, delimiter: bytes, stream_output: bool = False, show_status: bool = False) -> Optional[bytes]:
        data = b''
        timeout = 300
        max_len = len(delimiter)
        
        while timeout > 0:
            if data.endswith(delimiter):
                return data
            elif self.serial.inWaiting() > 0:
                timeout = 300
                data += self.serial.read(1)

                if stream_output:
                    sys.stdout.buffer.write(data[:-1])
                    sys.stdout.buffer.flush()
                    data = data[-max_len:]
                elif show_status:
                    self.transfer_status()
            else:
                timeout -= 1
                time.sleep(0.01)

    def boot(self):
        data = b''
        self.send_ctrl_c()
        self.until_nothing_in_waiting()
        time.sleep(.5)

        if not self.read_until(self.send_ctrl_d()):
            raise Exception('REPL: could not soft reboot')

        output_status = True
        self.boot_status = True

        while self.boot_status and output_status:
            if self.serial.inWaiting():
                sys.stdout.buffer.write((data := data[-15:] + self.serial.read(1))[-1:])
                sys.stdout.buffer.flush()
                output_status = not data.endswith(b'\r\nMicroPython v') and not data.endswith(b'.\r\n>>>')
        
        if not output_status:
            sys.stdout.buffer.write(b'\r<<< Program terminated\r\n')
        elif not self.boot_status:
            sys.stdout.buffer.write(b'\r\n<<< Program terminated with <KeyboardInterrupt Exception>\r\n')
        
        self.boot_status = False

    def __enter__(self):
        self.send_ctrl_c()
        self.until_nothing_in_waiting()

        for _ in range(0, 5): 
            if self.read_until(self.send_ctrl_a()):
                break

            time.sleep(0.01)
        else:
            raise Exception('Terminal: could not enter raw-REPL mode')

        return self.__terminal

    def __exit__(self, a, b, c):
        self.send_ctrl_b()

    def __terminal(self, command: str, stream_output: bool = False) -> Optional[str]:
        command = textwrap.dedent(command) 

        if not isinstance(command, bytes):
            command = bytes(command, encoding='utf-8')

        for i in range(0, len(command), BUFFER_SIZE):
            if not stream_output:
                self.transfer_status()

            self.serial.write(command[i: min(i + BUFFER_SIZE, len(command))])
            time.sleep(0.0001)

        if not self.read_until(self.send_ok()):
            raise Exception('Terminal: could not execute command')

        data = self.read_until(b'\x04', stream_output=stream_output, show_status=not stream_output)

        if not data:
            self.send_ctrl_d()
            raise Exception('Terminal: timeout waiting for first EOF reception')

        exception = self.read_until(b'\x04')

        if not exception:
            self.send_ctrl_d()
            raise Exception('Terminal: timeout waiting for second EOF reception')

        data, exception = (data[:-1].decode('utf-8'), exception[:-1].decode('utf-8'))

        if exception:
            reason = 'Traceback (most recent call last):'
            traceback = exception.split(reason)
            
            if len(traceback) == 2:
                for call in traceback[1][:-2].split('\\r\\n'):
                    reason += f'{call}\n'

                raise Exception('\r' + reason.strip())
            else:
                raise Exception('\r' + exception)

        return data.strip()


class FileSystem(object):
    pyboard: Pyboard

    def __init__(self, pyboard: Pyboard):
        self.pyboard = pyboard

    def checksum(self, source: str, data: str) -> str:
        output = self.terminal(f"""
            def checksum(data):
                v = 21
                for c in data.decode('utf-8'):
                    v ^= ord(c)
                return v
            
            with open('{source}', 'rb') as fh:
                print(checksum(fh.read()))
        """)

        if isinstance(data, bytes):
            data = data.decode('utf-8')

        v = 21
        for c in data:
            v ^= ord(c)

        if int(v) == int(output):
            return 'OK'
        
        return f'{v} != {output}'

    def get(self, filename: str) -> Tuple[bytes, bool]:
        if not filename.startswith('/'):
            filename = '/' + filename

        output = self.terminal(f"""
            import sys
            import ubinascii
            with open('{filename}', 'rb') as infile:
                while True:
                    result = infile.read({BUFFER_SIZE})
                    if result == b'':
                        break
                    sys.stdout.write(ubinascii.hexlify(result))
        """)
        output = binascii.unhexlify(output)

        if filename.endswith('.mpy'):
            return (output, '???')

        return (output, self.checksum(filename, output))

    def download(self, source: str, destination: str) -> str:
        output, checksum = self.get(source)

        with open(destination, 'wb') as fh:
            fh.write(output)
            
        return checksum

    def put(self, filename: str, data: bytes) -> Tuple[str, bool]:
        if not filename.startswith('/'):
            filename = '/' + filename

        if not isinstance(data, bytes):
            data = bytes(data, encoding='utf8')

        try:
            if os.path.dirname(filename):
                self.mkdir(os.path.dirname(filename))

            with self.pyboard as terminal:
                size = len(data)
                terminal(f"""fh = open('{filename}', 'wb')""")

                for i in range(0, size, BUFFER_SIZE):
                    chunk_size = min(BUFFER_SIZE, size - i)
                    chunk = repr(data[i : i + chunk_size])
                    terminal(f"""fh.write({chunk})""")

                terminal("""fh.close()""")
        except Exception as e:
            raise e

        if filename.endswith('.mpy'):
            return (filename, '???')

        return (filename, self.checksum(filename, data))

    def upload(self, source: str, destination: str) -> str:
        with open(source, 'rb') as fh:
            _, checksum = self.put(destination, fh.read())

        return checksum

    def ls(self, dirname: str = '/') -> Tuple[int, List, str]:
        dirname = dirname.strip('./').strip('/')

        output = self.terminal(f"""
            try:        
                import os
                import json
            except ImportError:
                import uos as os
                import ujson as json

            def ls(dirname):
                e = []
                s = os.stat(dirname)
                if s[0] == 0x4000:
                    if not dirname.endswith('/'):
                        dirname += '/'
                    e.append((dirname, -1))
                    for t in os.ilistdir(dirname):
                        if dirname.startswith('/'):
                            dirname = dirname[1:]
                        if t[1] == 0x4000:
                            e.extend(ls(dirname + t[0] + '/'))
                        else:
                            e.append((dirname + t[0], os.stat(dirname + t[0])[6]))
                else:
                    e.append((dirname, s[6]))
                return sorted(e)
            
            try:
                s = 1
                r = ls('{dirname}')
                x = ''
            except Exception as e:
                s = 0
                r = [('{dirname}', -2)]
                x = str(e)

            print(json.dumps([s, r, x]))
        """)
        
        return json.loads(output)

    def rm(self, filename: str) -> Tuple[int, List, str]:
        if not filename.startswith('/'):
            filename = '/' + filename

        output = self.terminal(f"""
            try:        
                import os
                import json
            except ImportError:
                import uos as os
                import ujson as json

            def ls(dirname):
                e = []
                if not dirname.endswith('/'):
                    dirname += '/'
                for t in os.ilistdir(dirname):
                    if dirname.startswith('/'):
                        dirname = dirname[1:]
                    if t[1] == 0x4000:
                        e.append((dirname + t[0] + '/', -1))
                        e.extend(ls(dirname + t[0] + '/'))
                    else:
                        e.append((dirname + t[0], os.stat(dirname + t[0])[6]))
                return sorted(e, reverse=True)

            def rm(filename):
                r = []
                if os.stat(filename)[0] == 0x4000:
                    e = ls(filename)
                    if filename != '/':
                        e.append((filename.strip('/'), -1))
                    for f, s in e:
                        if not s == -1:
                            try:
                                os.remove(f)
                                r.append((f, 1, ''))
                            except Exception as e:
                                r.append((f, 0, str(e)))
                    for f, s in e:
                        if s == -1:
                            try:
                                os.rmdir(f)
                                r.append((f, 1, ''))
                            except Exception as e:
                                r.append((f, 0, str(e)))
                else:
                    try:
                        os.remove(filename)
                        r.append((filename, 1, ''))
                    except Exception as e:
                        r.append((filename, 0, str(e)))
                return r

            try:
                s = 1
                r = rm('{filename}')
                x = ''
            except Exception as e:
                s = 0
                r = [('{filename}', 0, str(e))]
                x = str(e)

            print(json.dumps([s, r, x]))
        """)

        return json.loads(output)

    def mkdir(self, dirname: str) -> List:
        if not dirname.startswith('/'):
            dirname = '/' + dirname
        
        if dirname.endswith('/'):
            dirname = dirname[:-1]

        output = self.terminal(f"""
            try:        
                import os
                import json
            except ImportError:
                import uos as os
                import ujson as json

            r = []
            d = []
            for zd in str('{dirname}').split('/'):
                if not zd:
                    continue
                d.append(zd)
                zd = '/'.join(d)
                try:
                    os.mkdir(zd)
                    r.append(('/' + zd, 1))
                except Exception as e:
                    if str(e).find('EEXIST'):
                        r.append(('/' + zd, 1))
                    else:
                        r.append(('/' + zd, 0, str(e)))

            print(json.dumps(r))
        """)

        return json.loads(output)

    def launch(self, filename: str):
        try:
            self.terminal(f"""
                with open('{filename}', 'r') as fh:
                    exec(fh.read())
            """, stream_output=True)
        except Exception as e:
            print(str(e))

    def terminal(self, command: str, stream_output: bool = False) -> str:
        with self.pyboard as terminal:
            try:
                return terminal(command, stream_output=stream_output)
            except Exception as e:
                raise e
    

class Picowatch(object):

    def __init__(self, pyboard: Pyboard):
        self.filesystem = FileSystem(pyboard)
        signal.signal(signal.SIGINT, lambda signum, frame: self.interrupt())

    def boot(self):
        self.filesystem.pyboard.boot()

    def system(self):
        self.terminal("""
            import os
            import gc
            print('Board:', os.uname().machine, os.uname().version)
            print('Free memory:', round(gc.mem_free() / 1024, 2), 'kb.')
        """)

    def reset(self):
        self.terminal("""
            import machine
            machine.soft_reset()
        """)
        self.interrupt()
    
    def flash(self):
        self.terminal("""
            import machine
            machine.bootloader()
        """)
        self.interrupt()

    def interrupt(self):
        self.filesystem.pyboard.send_ctrl_c()
        self.filesystem.pyboard.until_nothing_in_waiting()

    def terminal(self, command: str):
        self.filesystem.terminal(command, stream_output=True)

    def internal_ls(self, filepath: str):
        queue = []

        if filepath == '/':
            filepath = LISTENING_TO.replace(os.sep, '/')
        else:
            filepath = os.path.join(LISTENING_TO, filepath.strip('./').strip('/')).replace(os.sep, '/')

        if os.path.isfile(filepath):
            queue = [(filepath, os.stat(filepath)[6])]
        elif os.path.isdir(filepath):
            def ls(dirname: str):
                e = []

                if os.path.isdir(dirname):
                    if not dirname.endswith('/'):
                        dirname += '/'

                    for filename in os.listdir(dirname):
                        if filename.startswith('.'):
                            continue

                        filename = dirname + filename

                        if os.path.isdir(filename):
                            e.extend(ls(filename))
                        else:
                            e.append((filename, os.stat(filename)[6]))
                return e

            queue = ls(filepath)

        return queue

    def listing(self, filepath: str = '/'):
        filepath = filepath.strip('./')
        tab = Tab(4, 50, 15, nb_columns=4)
        tab.head('[ ]', 'Filename', 'Size (kb)', 'Exception')
        status, output, exception = self.filesystem.ls(filepath)

        if status:
            for filename, size in output:
                if size == -1:
                    tab.line('[*]', filename, '-')
                else:
                    tab.line('[*]', filename, f'{round(size / 1024, 2)} kb')
        else:
            tab.line('[?]', filepath, '', str(exception))

    def contents(self, filename: str):
        filename = filename.strip('./').strip('/')
        content, _ = self.filesystem.get(filename)
        print('-' * 50)

        for ln in content.decode('utf-8').split('\n'):
            print(ln)

    def upload(self, filepath: str):
        tab = Tab(4, 50, 15, 15, nb_columns=5)
        tab.head('[ ]', 'Filename', 'Size (kb)', 'Checksum', 'Exception')

        for source, size in self.internal_ls(filepath):
            destination = source.replace(LISTENING_TO.replace(os.sep, '/'), '').strip('/')

            try:
                tab.line('[↑]', destination, f'{round(size / 1024, 2)} kb', self.filesystem.upload(source, destination))
            except Exception as e:
                tab.line('[?]', destination, '', '', str(e))

    def download(self, filepath: str):
        tab = Tab(4, 50, 15, nb_columns=4)
        tab.head('[ ]', 'Filename', 'Checksum', 'Exception')
        status, output, exception = self.filesystem.ls(filepath.strip('./').strip('/'))

        if status:
            for remote, size in output:
                if size == -1:
                    os.makedirs(os.path.join(LISTENING_TO, remote), 777, exist_ok=True)

            for remote, size in output:
                destination = os.path.join(LISTENING_TO, remote).replace(os.sep, '/')

                if not size == -1:
                    try:
                        tab.line('[↓]', remote, self.filesystem.download(remote, destination))
                    except Exception as e:
                        tab.line('[?]', remote, '', str(e))
        else:
            tab.line('[?]', filepath, '', exception)

    def delete(self, filepath: str):
        tab = Tab(4, 50, nb_columns=3)
        tab.head('[ ]', 'Filename', 'Exception')
        status, output, exception = self.filesystem.rm(filepath.strip('./'))

        if status:
            for filename, checked, exception in output:
                if checked:
                    tab.line('[-]', filename)
                else:
                    tab.line('[?]', filename, exception)
        else:
            tab.line('[?]', filepath, exception)

    def compare(self, filepath: str, use_vim: bool = True):
        content, _ = self.filesystem.get(filepath.strip('./').strip('/'))
        fh, tempname = tempfile.mkstemp('.py')

        try:
            with os.fdopen(fh, 'wb') as tmp:
                tmp.write(content)
            
            if use_vim:
                subprocess.call(['vim', '-d', os.path.join(LISTENING_TO, filepath), tempname], shell=True)
            else:
                subprocess.call(['code', '--diff', os.path.join(LISTENING_TO, filepath), tempname], shell=True)
        finally:
            input('Press Enter to delete temp file.')
            os.remove(tempname)
    
    def status(self, return_output: bool = False):
        message = ''
        changes = []

        try:
            subprocess.check_output(['git', 'add', '-A'], stderr=subprocess.STDOUT)
            output = subprocess.check_output(['git', 'status', '-s'], stderr=subprocess.STDOUT)

            for filename in [f.strip() for f in output.decode('utf-8').split('\n')]:
                if not filename:
                    continue

                columns = filename.split(' ')

                if len(columns) == 2:
                    status, filename = columns
                elif len(columns) == 3:
                    status, _, filename = columns
                elif len(columns) == 5:
                    changes.append((1, columns[4]))
                    changes.append((-1, columns[2]))
                    continue
                else:
                    continue

                if status in ['A', 'M', '??']:
                    changes.append((1, filename))
                elif status == 'D':
                    changes.append((-1, filename))
        except Exception as e:
            try:
                message = e.output.decode('utf-8').strip()
            except:
                message = str(e).strip()
        finally:
            if message:
                raise Exception(message)

            if return_output:
                return changes

            if changes:
                tab = Tab(4, nb_columns=2)
                tab.head('[ ]', 'Filename')

                for status, filename in changes:
                    if status == 1:
                        tab.line('[+]', filename)
                    else:
                        tab.line('[-]', filename)
            else:
                print('Repository is clean')

    def commit(self, message: str = ''):
        changes = self.status(return_output=True)

        if changes:
            tab = Tab(4, 30, 15, 15, nb_columns=5)
            tab.head('[ ]', 'Filename', 'Size (kb)', 'Checksum', 'Exception')

            for filepath in [filename for status, filename in changes if status == -1]:
                filepath = filepath.strip('/')
                status, output, exception = self.filesystem.rm(filepath)

                if status:
                    for filename, checked, exception in output:
                        if checked:
                            tab.line('[-]', filename, '', 'DELETED')
                        else:
                            tab.line('[?]', filename, '', '', exception)
                else:
                    tab.line('[?]', filepath, '', '', exception)

            queue = []

            for filepath in [filename for status, filename in changes if status == 1]:
                queue.extend(self.internal_ls(filepath))

            for source, size in queue:
                destination = source.replace(LISTENING_TO.replace(os.sep, '/'), '').strip('/')

                try:
                    tab.line('[↑]', destination, f'{round(size / 1024, 2)} kb', self.filesystem.upload(source, destination))
                except Exception as e:
                    tab.line('[?]', destination, '', '', str(e))

            print('-' * 50)

            if not message:
                message = 'Synchronize Pyboard along with associated commit(s)'
            else:
                message = message.strip('"').strip("'")

            try:
                output = subprocess.check_output(['git', 'commit', '-am', message], stderr=subprocess.STDOUT)

                for line in output.decode('utf-8').split('\n'):
                    print(line)
            except Exception as e:
                try:
                    message = e.output.decode('utf-8').strip()
                except:
                    message = str(e).strip()
        else:
            print('Pyboard is up to date')
        
    def compile(self, filename: str):
        _, error = mpy_cross.run(filename, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True).communicate()

        if error:
            print(error.decode('utf-8'))
        else:
            print(f'Python file "{filename}" compile to .mpy')

    def install(self, package_name: str):
        self.terminal(f"""
            import mip
            mip.install('{package_name}')  
        """)

    def test(self, filename: str):
        with open(os.path.join(LISTENING_TO, filename), 'r') as fh:
            self.filesystem.terminal(fh.read(), stream_output=True)

    def launch(self, filename: str):
        self.filesystem.launch(filename)


print('Welcome to Picowatch Terminal')
print(f'Listening to project: {LISTENING_TO.replace(os.sep, "/")}/')
picowatch = False

try:
    env = dotenv_values('.picowatch')
    picowatch = Picowatch(Pyboard(env["DEVICE"], env["BAUDRATE"]))
    print(f'Connected automatically to device: {env["DEVICE"]} at a baudrate of: {env["BAUDRATE"]}')
except:
    while not picowatch:
        print('-' * 50)
        device = input('Port: ').strip()
        baudrate = input('Baudrate (115200): ').strip() or 115200

        try:
            picowatch = Picowatch(Pyboard(device, baudrate))
            print('-' * 50)
            print(f'Connected to device: {device} and baudrate: {baudrate}')

            with open(os.path.join(LISTENING_TO, '.picowatch'), 'w+') as fh:
                fh.write(f'DEVICE = "{device}"\n')
                fh.write(f'BAUDRATE = {baudrate}\n')
        except Exception as e:
            print(str(e))

print('-' * 50)
picowatch.interrupt()

while True:
    try:
        unmessage = input('>>> ').strip()

        for message in unmessage.split('&'):
            try:
                match message.strip().split(' '):
                    case ['?' | 'help']:
                        print('These are common Picowatch keywords:')
                        tab = Tab(12, 10, 32, nb_columns=4)
                        tab.head('Keywdords', 'Shortcut', 'Parameters', 'Description')
                        tab.line('help', '?', '', 'Show keywords and their description.')
                        tab.line('modules', '??', '', 'List availables modules on the Pyboard.')
                        tab.line('boot', '.', '', 'Perform a soft reset and run main.py (if exists) in REPL mode.')
                        tab.line('test', '!', '[<file>] (default: main.py)', 'Run a script from PC on the Pyboard and print out the results in raw-REPL mode.')
                        tab.line('run', '!!', '[<file>] (default: main.py)', 'Run a script on the Pyboard and print out the results in raw-REPL mode.')
                        tab.line('ctrl + C', '', '', 'Interrupts the currently running code in REPL or raw-REPL mode.')
                        tab.line('ctrl + D', 'exit', '', 'Exit Picowatch Terminal.')
                        tab.line('ctrl + Z', 'exit', '', 'Same as ctrl + D, Exit Picowatch Terminal.')
                        tab.line('system', 'os', '', 'Pyboard name and version.')
                        tab.line('reset', 'rs', '', 'Perform a soft reset from the REPL.')
                        tab.line('flash', 'fl', '', 'Perform a flash disk from the REPL.')
                        tab.line('scan', 'ls', '[<path>] (default: /)', 'List information about the file(s) on the Pyboard.')
                        tab.line('edit', 'vim', '<file> [<use vim>]', 'Edit specified file from the PC (vim or vscode is required).')
                        tab.line('source', 'cat', '<file>', 'Concatenate source code to standard output.')
                        tab.line('delete', 'rm', '<path>', 'Delete file or directory contents on the Pyboard.')
                        tab.line('upload', 'put', '<path>', 'Upload file or directory contents from the PC to the Pyboard.')
                        tab.line('download', 'get', '<path>', 'Download file or directory contents from the Pyboard to the PC. Warning: this may cause file corruption.')
                        tab.line('compare', 'diff', '<file> [<use vim>]', 'Compare source code from PC with source code from the Pyboard (vim or vscode is required).')
                        tab.line('compile', 'mpy', '<python file>', 'Compile source file to mpy file.')
                        tab.line('install', 'mip', '<package name>', 'Install packages from micropython-lib and from third-party sites (including GitHub) - *Network-capable boards only.')
                        tab.line('status', 'mod', '', 'Show the working tree status (Git is required).')
                        tab.line('commit', 'sync', '[<message>] (default: "")', 'Synchronize Pyboard along with associated commit(s) (Git is required).')
                    case ['??' | 'modules']:
                        picowatch.terminal(f'help("modules")')
                    case ['os' | 'system']:
                        picowatch.system()
                    case ['ls' | 'scan', *file]:
                        picowatch.listing(file[0] if file else '/')
                    case ['vim' | 'edit', file, *use_vim]:
                        if len(use_vim) > 0:
                            subprocess.call(['vim', file], shell=True)
                        else:
                            subprocess.call(['code', file], shell=True)
                    case ['cat' | 'source', file]:
                        picowatch.contents(file)
                    case ['rm' | 'delete', path]:
                        picowatch.delete(path)
                    case ['put' | 'upload', path]:
                        picowatch.upload(path)
                    case ['get' | 'download', path]:
                        picowatch.download(path)
                    case ['diff' | 'compare', file, *use_vim]:
                        picowatch.compare(file, use_vim=len(use_vim) > 0)
                    case ['mod' | 'status']:
                        picowatch.status(return_output=False)
                    case ['sync' | 'commit', *message]:
                        picowatch.commit(message=' '.join(message).strip())
                    case ['mpy' | 'compile', file]:
                        picowatch.compile(file)
                    case ['mip' | 'install', package_name]:
                        picowatch.install(package_name)
                    case ['!' | 'test', *file]:
                        picowatch.test(file[0] if file else 'main.py')
                    case ['!!' | 'run', *file]:
                        picowatch.launch(file[0] if file else 'main.py')
                    case ['.'| 'boot']:
                        picowatch.boot()
                    case ['rs' | 'reset']:
                        picowatch.reset()
                    case ['fl' | 'flash']:
                        picowatch.flash()
                    case ['exit']:
                        sys.exit('Picowatch Terminal disconnected!')
                    case _:
                        if message:
                            print(f'Picowatch: "{message}" does not matched any keywords. See "help" for more informations.')
            except Exception as e:
                print(str(e))
    except (KeyboardInterrupt, EOFError):
        sys.exit('Picowatch Terminal disconnected!')
