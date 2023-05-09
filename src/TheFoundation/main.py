from libs.routerhttp import HTTP, RouterHTTP


def a(http: HTTP) -> int:
    http.response.content = 'Not Found me...'

def b(http: HTTP) -> int:
    if http.response.template('templates/index.html'):
        return HTTP.STATUS_OK
    
    return HTTP.STATUS_NOT_FOUND

def c(http: HTTP) -> int:
    if http.response.download('templates/index.html'):
        return HTTP.STATUS_OK
    
    return HTTP.STATUS_NOT_FOUND

app = RouterHTTP(ssid='SFR-a9c8', password='abc123de45f6')
#rhttp = RouterHTTP(ssid='PMD', password="Primadiag2021'...")

app.map('GET|POST', '/', b)

app.listen()
