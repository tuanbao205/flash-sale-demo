import json, os, secrets
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from core import Sale, Rejected
from openapi import SPEC
ROOT=Path(__file__).resolve().parent
sale=Sale(str(ROOT/'sale.db'))
ADMIN=os.environ.get('DEMO_ADMIN_KEY') or secrets.token_urlsafe(24)
class DemoServer(ThreadingHTTPServer):
    request_queue_size = 256
    daemon_threads = True

class Handler(BaseHTTPRequestHandler):
    def send(self, status, obj):
        content=json.dumps(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(content)))
        self.end_headers(); self.wfile.write(content)
    def do_GET(self):
        if self.path=='/api/stats': return self.send(200,sale.stats())
        if self.path=='/openapi.json': return self.send(200,SPEC)
        pages={'/':'index.html','/docs':'swagger.html','/docs/':'swagger.html','/swagger-ui':'swagger.html'}
        if self.path not in pages: return self.send(404,{'error':'NOT_FOUND'})
        content=(ROOT/'static'/pages[self.path]).read_bytes()
        self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(content)
    def do_POST(self):
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<0 or size>8192: raise Rejected('BODY_TOO_LARGE',413)
            body=json.loads(self.rfile.read(size) or '{}')
            if not isinstance(body,dict): raise Rejected('INVALID_JSON',400)
            session=self.headers.get('Authorization','').removeprefix('Bearer ')
            ip=self.client_address[0] # never trust arbitrary X-Forwarded-For
            if self.path=='/api/demo/login':
                sale.limit(('login-ip',ip),300)
                result={'session':sale.session(body.get('user',''),body.get('device',''))}
            elif self.path=='/api/join': result=sale.join(session,ip)
            elif self.path=='/api/ticket': result=sale.ticket(session)
            elif self.path=='/api/buy': result=sale.buy(session,body.get('ticket',''),self.headers.get('Idempotency-Key',''),ip)
            elif self.path=='/api/admin/draw':
                if not secrets.compare_digest(self.headers.get('X-Admin-Key',''),ADMIN): raise Rejected('ADMIN_REQUIRED')
                result=sale.draw()
            else: raise Rejected('NOT_FOUND',404)
            self.send(200,result)
        except Rejected as e: self.send(e.status,{'error':e.code})
        except (ValueError,TypeError,AttributeError): self.send(400,{'error':'INVALID_REQUEST'})
        except Exception:
            self.send(500,{'error':'INTERNAL_ERROR'})
    def log_message(self,*args): pass
if __name__=='__main__':
    print('Demo: http://localhost:8080',flush=True)
    print('Swagger UI: http://localhost:8080/docs',flush=True)
    print('Admin key (local demo): '+ADMIN,flush=True)
    print('Restart clears queue/sessions, preserves orders. Delete sale.db* ONLY to reset demo.',flush=True)
    DemoServer(('127.0.0.1',8080),Handler).serve_forever()
