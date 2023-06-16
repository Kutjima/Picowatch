import json

from libs.webapp import asyncio, HTTP, WebSocket, Schedule, RouterHTTP


app = RouterHTTP()

for crendential in json.load(open('/credentials.json')):
    if app.setup(crendential['ssid'], crendential['password'], timezone=2):
        break

if not app.is_connected:
    raise RuntimeError('Connection failed to WiFi')

app.mount(path='/www/public', name='/public')

@app.http(methods='GET|POST', pattern='/')
async def c(http: HTTP) -> int:
    status_code, content = http.response.template('www/templates/ws.html')
    http.response.content = content

    # async def backg_task():
    #     for i in range(100):
    #         print('bg:', i)
    #         await asyncio.sleep(0.2)

    # http.add_background_task(backg_task)

    return status_code

@app.http(methods='GET|POST', pattern='/templating')
async def d(http: HTTP) -> int:
    status_code, content = http.response.template('www/templates/index.html', {
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
    return status_code

@app.http(methods='GET|POST', pattern='/download')
async def d(http: HTTP) -> int:
    return http.response.attachment('www/public/faviscon.png')

@app.websocket(port=8000, max_tasks=2)
async def e(websocket: WebSocket):
    while True:
        try:
            message = await websocket.recv()
            # print('From:', websocket.address, ' - ', message)
            # websocket.send(str(websocket))
            websocket.broadcast(str(websocket.websockets))
        except WebSocket.WebSocketDisconnect:
            break
        except Exception as e:
            print(str(e))

@app.schedule(hour=3)
async def f(schedule: Schedule):
    print('Triggered:', schedule.name, 'at:', schedule.localtime)
    schedule.stop()
    await asyncio.sleep(0)

@app.schedule(second=0)
async def f(schedule: Schedule):
    print('Triggered:', schedule.name, 'at:', schedule.localtime)
    schedule.next(second=5)
    await asyncio.sleep(0)


app.listen()
