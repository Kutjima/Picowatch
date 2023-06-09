import json

from libs.routerhttp import asyncio, HTTP, Websocket, RouterHTTP


app = RouterHTTP()

for crendential in json.load(open('/credentials.json')):
    if app.connect_wlan(crendential['ssid'], crendential['password']):
        break

if not app.is_connected:
    raise RuntimeError('Connection failed to WiFi')

app.mount(path='/www/public', name='/public')


@app.status(HTTP.STATUS_NOT_FOUND)
def a(http: HTTP):
    http.response.content = 'Not Found me...'

@app.status(HTTP.STATUS_INTERNAL_SERVER_ERROR)
def b(http: HTTP):
    pass

@app.http('GET|POST', '/')
def c(http: HTTP) -> int:
    status, content = http.response.template('www/templates/ws.html')

    http.response.content = content

    async def aaa():
        for i in range(100):
            print('bg:', i)
            await asyncio.sleep(0.2)

    http.add_background_task(aaa)

    if status:
        return HTTP.STATUS_OK

    return HTTP.STATUS_INTERNAL_SERVER_ERROR

@app.http('GET|POST', '/template')
def d(http: HTTP) -> int:
    status, content = http.response.template('www/templates/index.html', {
        'metadata': {
            'uuid_0': {
                'title': 'Hello World 1!',
                'description': 'Hello my world 1!'
            },
            'uuid_1': {
                'title': 'Hello World 2!',
                'description': 'Hello my world 2!'
            },
            'uuid_2': {
                'title': 'Hello World 3!',
                'description': 'Hello my world 3!'
            }
        },
    })

    http.response.content = content

    if status:
        return HTTP.STATUS_OK

    return HTTP.STATUS_INTERNAL_SERVER_ERROR

Websocket.set_max_connections(2)

@app.websocket(8000)
async def e(websocket: Websocket):
    while True:
        if (message := websocket.recv()) is not None:
            print('From:', websocket.IP, ' - ', message)
            # websocket.send(str(websocket))
            websocket.broadcast(str(websocket.connections_alive))
        
        # important to unlock connections
        await asyncio.sleep(0)

app.listen()
