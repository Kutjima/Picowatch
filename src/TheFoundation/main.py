import gc
import json

from libs.thefoundation import asyncio, status, TheFoundation, Request, WebSocket, Schedule


app = TheFoundation()

for crendential in json.load(open('/credentials.json')):
    if app.connect(crendential['ssid'], crendential['password'], timezone=2):
        break
else:
    raise RuntimeError('Connection failed to WiFi')

app.mount(path='/www/public', name='/public')

@app.map(methods='GET', pattern='/')
async def a(request: Request) -> str:
    return request.redirect(to='/ws')

@app.map(methods='GET', pattern='/download')
async def b(request: Request) -> str:
    #return request.content_to_attachment('/www/public/favicon.png')
    return request.abort(status.STATUS_503_SERVICE_UNAVAILABLE)

@app.map(methods='GET', pattern='/favicon.png')
async def b(request: Request) -> str:
    return request.content_to_media('/www/public/favicon.png', {'Cache-Control': 'max-age=86400, must-revalidate'})

@app.map(methods='GET', pattern='/ws')
async def c(request: Request) -> str:
    return request.content_to_template('www/templates/ws.html')

@app.map(methods='GET', pattern='/json')
async def d(request: Request) -> str:
    return request.content_to_json({
        'app': 'The Foundation',
        'version': 0.2
    })

@app.map(methods='GET|POST', pattern='/templating')
async def d(request: Request) -> str:
    return request.content_to_template('www/templates/index.html', {
        'title': 'The Foundation',
        'version': 0.2,
        'POST': request.POST
    })

@app.websocket(port=8000, max_connections=2)
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
            print(e)
            break

# @app.schedule(second=[0, 15, 30, 45])
# async def f(schedule: Schedule):
#     print('Triggered:', schedule.name, 'at:', schedule.localtime)
#     print('Free memory:', round(gc.mem_free() / 1024, 2), 'kb.', schedule.n)

#     await asyncio.sleep(0)

app.listen()
