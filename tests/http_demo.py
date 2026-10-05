"""Run against a fresh local server; requires its printed admin key."""
import argparse,json,urllib.request,urllib.error
from concurrent.futures import ThreadPoolExecutor
p=argparse.ArgumentParser();p.add_argument('--admin-key',required=True);a=p.parse_args()
def post(path,body,session='',extra=None):
    req=urllib.request.Request('http://127.0.0.1:8080'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+session,**(extra or {})})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
    except urllib.error.HTTPError as e:return json.load(e)
users=[]
for i in range(100):
    session=post('/api/demo/login',{'user':f'http-{i}','device':f'http-device-{i}'})['session']
    assert post('/api/join',{},session)['status']=='WAITING'
    users.append(session)
print(post('/api/admin/draw',{},extra={'X-Admin-Key':a.admin_key}))
tickets=[post('/api/ticket',{},s)['ticket'] for s in users]
def buy(i):return post('/api/buy',{'ticket':tickets[i]},users[i],{'Idempotency-Key':f'http-key-{i}'})
with ThreadPoolExecutor(max_workers=30) as pool: results=list(pool.map(buy,range(100)))
assert sum(r.get('status')=='ORDER_CREATED' for r in results)==100,results
retry=buy(0);assert retry.get('replayed') is True
invalid=post('/api/buy',{'ticket':'fake'},users[0],{'Idempotency-Key':'bad'})
assert invalid.get('error')=='INVALID_TICKET'
with urllib.request.urlopen('http://127.0.0.1:8080/api/stats') as r:stats=json.load(r)
assert stats['stock']==0 and stats['orders']==100 and stats['invariant_ok']
print(json.dumps({'stats':stats,'retry':retry,'invalid_ticket':invalid},indent=2))
print('HTTP demo PASS: 100 orders, stock 0, replay safe, forged ticket rejected.')
