"""Loopback-published round-robin reverse proxy for the two local API replicas."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import itertools
import urllib.request
import urllib.error
turn=itertools.cycle(['api','api2'])
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def dispatch(self):
        self.connection.settimeout(2)
        body=self.rfile.read(min(int(self.headers.get('Content-Length',0)),65536))
        try:
            request=urllib.request.Request('http://'+next(turn)+':8080'+self.path,
              data=body if self.command!='GET' else None,method=self.command,
              headers={k:v for k,v in self.headers.items() if k.lower() not in {'host','connection','content-length'}})
            try:response=urllib.request.urlopen(request,timeout=19)
            except urllib.error.HTTPError as exc:response=exc
            data=response.read();self.send_response(response.code)
            for key,value in response.headers.items():
                if key.lower() not in {'server','date','connection','transfer-encoding','content-length'}:self.send_header(key,value)
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        except Exception:
            data=b'{"status":"OUTCOME_UNKNOWN","message":"Response pending; refresh the same operation."}'
            self.send_response(202);self.send_header('Content-Length',str(len(data)));self.end_headers()
            try:self.wfile.write(data)
            except Exception:pass
    do_GET=dispatch;do_POST=dispatch;do_PATCH=dispatch
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
