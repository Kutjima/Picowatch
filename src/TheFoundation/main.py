import json

from libs.routerhttp import HTTP, RouterHTTP


for crendential in json.load(open('/credentials.json')):
    app = RouterHTTP(crendential['ssid'], crendential['password'], ignore_exception=True)

    if app.wlan.isconnected():
        break

if app.wlan.isconnected() == False:
    raise RuntimeError('Connection failed to WiFi')


@app.map(404)
def a(http: HTTP) -> int:
    http.response.content = 'Not Found me...'

@app.map('GET|POST', '/')
def b(http: HTTP) -> int:
    if (content := http.response.template('templates/index.html', {
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
    })):
        http.response.content = content
        return HTTP.STATUS_OK
    
    return HTTP.STATUS_NOT_FOUND

@app.map('GET', '/(download|dl)/(something)?')
def c(http: HTTP, access: str, nothing: str = '11111') -> int:
    if http.response.template('templates/index.html'):
        return HTTP.STATUS_OK
    
    return HTTP.STATUS_NOT_FOUND

app.listen()
