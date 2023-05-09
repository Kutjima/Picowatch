from libs.routerhttp import HTTP, RouterHTTP


app = RouterHTTP(ssid='SFR-xxxx', password='abc123de45f6')


@app.map(404)
def a(http: HTTP) -> int:
    http.response.content = 'Not Found me...'

@app.map('GET|POST', '/')
def b(http: HTTP) -> int:
    if http.response.template('templates/index.html'):
        return HTTP.STATUS_OK
    
    return HTTP.STATUS_NOT_FOUND

@app.map('GET', '/(download|dl)/(something)?')
def c(http: HTTP, access: str, nothing: str = '11111') -> int:
    if http.response.template('templates/index.html'):
        return HTTP.STATUS_OK
    
    return HTTP.STATUS_NOT_FOUND

app.listen()
