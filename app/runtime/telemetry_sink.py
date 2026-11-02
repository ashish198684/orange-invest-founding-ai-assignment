"""Local OTLP/protobuf receiver; records decoded SDK spans, never exports remotely."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        message=ExportTraceServiceRequest()
        message.ParseFromString(self.rfile.read(min(int(self.headers.get('Content-Length',0)),2000000)))
        path=Path(os.getenv('RUNTIME_STATE','data/runtime'))/'otel.jsonl'
        with path.open('a') as f:f.write(json.dumps(MessageToDict(message))+'\n')
        self.send_response(200);self.send_header('Content-Length','0');self.end_headers()
    def do_GET(self):self.send_response(200);self.end_headers()
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',4318),Handler).serve_forever()
