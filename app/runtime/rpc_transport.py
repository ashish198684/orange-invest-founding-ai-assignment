"""Minimal killable HTTP child. No controller, DB, telemetry or permission logic."""
import json
import sys
import urllib.request
import urllib.error

def main():
    try:
        value=json.loads(sys.stdin.buffer.read(131072))
        request=urllib.request.Request(value['url'],data=json.dumps(value['body']).encode(),headers={
            'Content-Type':'application/json','X-Provider-Key':value['secret'],'traceparent':value['parent']})
        try:
            with urllib.request.urlopen(request,timeout=15) as response:raw=response.read(1048577)
        except urllib.error.HTTPError as exc:raw=exc.read(1048577)
        if len(raw)>1048576:raise ValueError()
        result=json.loads(raw)
    except Exception:result={'error':'transport_unavailable','http_status':503}
    sys.stdout.write(json.dumps(result))

if __name__=='__main__':main()
