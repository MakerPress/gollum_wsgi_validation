import json

def application(environ, start_response):
    status = '200 OK'
    output = json.dumps({
       'auth_openid': environ['REMOTE_USER']
    }) 

    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)

    return [output]
