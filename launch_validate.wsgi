from subprocess import Popen
import json

URL = "http://localhost:8080/wsgi-bin/validate.wsgi?log_key=%s"
PROG_URL = "http://localhost:8080/wsgi-bin/monitor_.wsgi?log_key=%s"

def application(environ, start_response):
    status = '200 OK'
    key_log = "key1000"
    #
    # This next line starts the validate process by using curl
    # Since it doesn't block, it returns the results instantly
    # while launching the slow process
    #
    p = Popen(['curl', URL % key_log])
    
    output = json.dumps({
       'key_log': key_log,
       'prog_url': PROG_URL % key_log
    }) 

    response_headers = [('Content-type', 'text/plain'),
                        ('Content-Length', str(len(output)))]
    start_response(status, response_headers)

    return [output]
