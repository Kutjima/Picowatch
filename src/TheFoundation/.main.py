import json

from libs.routerhttp import HTTP, RouterHTTP


for crendential in json.load(open('/credentials.json')):
    app = RouterHTTP(crendential['ssid'], crendential['password'], ignore_exception=True)

    if app.wlan.isconnected():
        break

if app.wlan.isconnected() == False:
    raise RuntimeError('Connection failed to WiFi')

app.mount(path='/www/public', name='/public')


@app.map(HTTP.STATUS_NOT_FOUND)
def a(http: HTTP):
    http.response.content = 'Not Found me...'

@app.map(HTTP.STATUS_INTERNAL_SERVER_ERROR)
def b(http: HTTP):
    pass


@app.map('GET|POST', '/')
def c(http: HTTP) -> int:
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


@app.map('GET', '/(download|dl)\/?(attachment)?')
def d(http: HTTP, access: str, nothing: str = '') -> int:
    return http.response.attachment('www/public/favicon.png')

app.listen()
