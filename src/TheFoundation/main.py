from libs.routerhttp import RouterHttp


def a(response: RouterHttp.Response) -> int:
    response.content = 'Not Found me...'

def b(response: RouterHttp.Response) -> int:
    if response.template('index.html', {'hello': 'world'}):
        return response.RESPONSE_OK
    
    return response.RESPONSE_NOT_FOUND

def c(response: RouterHttp.Response) -> int:
    if response.download('index.html'):
        return response.RESPONSE_OK
    
    return response.RESPONSE_NOT_FOUND

rhttp = RouterHttp(ssid='SFR-a9c8', password='abc123de45f6')
rhttp.map(404, '', a)
rhttp.map('GET', '/hello/world', b)
rhttp.map('GET', '/download', c)

rhttp.listen()
