import redis
import json
from cgi import parse_qs, escape

status_log = redis.Redis(host="localhost", port=6379, db=0)

def application(environ, start_response):
    status = '200 OK'
    
    # Get the Redis log key from the command line
    qs = parse_qs(environ['QUERY_STRING'])
    log_key = qs.get('log_key', ["key1000"])[0]
    log_key = escape(log_key)

    # Pull out the status log and put into a list
    out = []
    for m in status_log.lrange(log_key,0,99):
       out.append(m)
    
    # Serialize log as JSON
    output = json.dumps(out) 

    response_headers = [('Content-type', 'text/plain'),
                        ('Content-Length', str(len(output)))]
    start_response(status, response_headers)

    return [output]
