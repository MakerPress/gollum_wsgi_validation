from subprocess import Popen
import json
import random
from cgi import parse_qs, escape


URL = "http://dev1.makerpress.com:8080/wsgi-bin/validate.wsgi?log_key=%s&root=%s"
PROG_URL = "http://dev1.makerpress.com:8080/wsgi-bin/monitor_validate.wsgi?log_key=%s"

def application(environ, start_response):
    status = '200 OK'


    # Get the Redis log key from the command line
    qs = parse_qs(environ['QUERY_STRING'])
    root = qs.get('root', ["book.asc"])[0]
    root = escape(root)


    log_key = "key%s" % str(random.randrange(0,1000))
    #
    # This next line starts the validate process by using curl
    # Since it doesn't block, it returns the results instantly
    # while launching the slow process
    #
    p = Popen(['curl', URL % (log_key,root)])
    
    output = json.dumps({
       'log_key': log_key,
       'root' : root,
       'callback_url': PROG_URL % log_key
    }) 

    response_headers = [('Content-type', 'text/plain'),
                        ('Content-Length', str(len(output)))]
    start_response(status, response_headers)

    return [output]
