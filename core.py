import sqlite3, threading, secrets, time, json, base64, hmac, hashlib
from collections import defaultdict, deque

class Rejected(Exception):
    def __init__(self, code, status=403):
        self.code, self.status = code, status

class Sale:
    def __init__(self, path):
        self.path = path
        self.secret = secrets.token_bytes(32)
        self.lock = threading.RLock()
        self.writer = threading.Semaphore(8)
        self.hits = defaultdict(deque)
        self.sessions = {}
        self.waiting = {}
        self.selected = set()
        self.drawn = False
        self.metrics = defaultdict(int)
        with self.connect() as db:
            db.executescript('''PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS stock(id INTEGER PRIMARY KEY, remaining INTEGER NOT NULL CHECK(remaining >= 0));
INSERT OR IGNORE INTO stock VALUES(1,100);
CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE, request_key TEXT NOT NULL UNIQUE, created REAL NOT NULL);
''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def session(self, user, device):
        # DEMO identity only: production requires authenticated, verified account.
        if not user or not device or len(user)>80 or len(device)>80:
            raise Rejected('INVALID_IDENTITY',400)
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.sessions[token] = (user, device)
        return token

    def identity(self, token):
        with self.lock:
            identity = self.sessions.get(token)
        if not identity:
            raise Rejected('LOGIN_REQUIRED',401)
        return identity

    def limit(self, key, maximum, seconds=10):
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and q[0] <= now-seconds:
                q.popleft()
            if len(q)>=maximum:
                self.metrics['rate_limited'] += 1
                raise Rejected('RATE_LIMITED',429)
            q.append(now)

    def join(self, session, ip):
        user, device = self.identity(session)
        with self.lock:
            if self.drawn:
                raise Rejected('REGISTRATION_CLOSED',409)
            if user in self.waiting:
                return {'status':'WAITING'}
            self.limit(('ip',ip),200)
            accounts = {u for u,d in self.waiting.items() if d==device}
            if len(accounts)>=2:
                self.metrics['device_blocked'] += 1
                raise Rejected('DEVICE_ACCOUNT_LIMIT')
            self.waiting[user]=device
        return {'status':'WAITING'}

    def draw(self):
        with self.lock:
            if self.drawn:
                raise Rejected('ALREADY_DRAWN',409)
            people=list(self.waiting)
            secrets.SystemRandom().shuffle(people)
            self.selected=set(people[:100])
            self.drawn=True
            return {'registered':len(people),'selected':len(self.selected)}

    def ticket(self, session):
        user,_=self.identity(session)
        with self.lock:
            if not self.drawn:
                return {'status':'WAITING'}
            if user not in self.selected:
                return {'status':'NOT_SELECTED'}
        payload=base64.urlsafe_b64encode(json.dumps({'user':user,'event':1,'exp':time.time()+600}).encode()).decode()
        sig=hmac.new(self.secret,payload.encode(),hashlib.sha256).hexdigest()
        return {'status':'SELECTED','ticket':payload+'.'+sig}

    def verify(self, ticket, user):
        try:
            payload,sig=ticket.split('.')
            expected=hmac.new(self.secret,payload.encode(),hashlib.sha256).hexdigest()
            data=json.loads(base64.urlsafe_b64decode(payload))
            if not hmac.compare_digest(sig,expected) or data['user']!=user or data['event']!=1 or data['exp']<time.time():
                raise ValueError()
            with self.lock:
                if user not in self.selected:
                    raise ValueError()
        except (ValueError,KeyError,TypeError):
            raise Rejected('INVALID_TICKET')

    def buy(self, session, ticket, request_key, ip):
        user,device=self.identity(session)
        self.verify(ticket,user)
        if not request_key or len(request_key)>120:
            raise Rejected('INVALID_IDEMPOTENCY_KEY',400)
        # Retry existing result before rate limiting; final transaction also checks again.
        with self.connect() as db:
            existing=db.execute('SELECT id,request_key FROM orders WHERE user_id=?',(user,)).fetchone()
            collision=db.execute('SELECT user_id FROM orders WHERE request_key=?',(request_key,)).fetchone()
        if collision and collision[0]!=user:
            raise Rejected('IDEMPOTENCY_KEY_CONFLICT',409)
        if existing:
            return {'status':'ORDER_CREATED','order_id':existing[0],'replayed':True}
        self.limit(('user',user),5)
        self.limit(('device',device),10)
        self.limit(('buy-ip',ip),200)
        if not self.writer.acquire(timeout=1):
            raise Rejected('BUSY_RETRY',503)
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT id FROM orders WHERE user_id=?',(user,)).fetchone()
            if existing:
                db.rollback()
                return {'status':'ORDER_CREATED','order_id':existing[0],'replayed':True}
            collision=db.execute('SELECT user_id FROM orders WHERE request_key=?',(request_key,)).fetchone()
            if collision:
                raise Rejected('IDEMPOTENCY_KEY_CONFLICT',409)
            updated=db.execute('UPDATE stock SET remaining=remaining-1 WHERE id=1 AND remaining>0').rowcount
            if updated!=1:
                raise Rejected('SOLD_OUT',409)
            order=secrets.token_hex(16)
            db.execute('INSERT INTO orders VALUES(?,?,?,?)',(order,user,request_key,time.time()))
            db.commit()
            return {'status':'ORDER_CREATED','order_id':order,'replayed':False}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
            self.writer.release()

    def stats(self):
        with self.connect() as db:
            stock=db.execute('SELECT remaining FROM stock WHERE id=1').fetchone()[0]
            orders=db.execute('SELECT count(*) FROM orders').fetchone()[0]
        with self.lock:
            return {'stock':stock,'orders':orders,'invariant_ok':stock+orders==100,'registered':len(self.waiting),'selected':len(self.selected),'drawn':self.drawn,'metrics':dict(self.metrics)}
