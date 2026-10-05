import sys, tempfile, unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Sale, Rejected
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.sale=Sale(str(Path(self.tmp.name)/'test.db'))
    def tearDown(self): self.tmp.cleanup()
    def participant(self,i):
        token=self.sale.session('u'+str(i),'d'+str(i))
        self.sale.join(token,'ip'+str(i))
        return token
    def test_1000_requests_database_last_barrier(self):
        # Inject faulty admission permitting 1000 tickets: DB still must enforce 100.
        sessions=[self.participant(i) for i in range(1000)]
        self.sale.draw()
        self.sale.selected=set(self.sale.waiting)
        tickets=[self.sale.ticket(s)['ticket'] for s in sessions]
        def call(i):
            try: return self.sale.buy(sessions[i],tickets[i],'k'+str(i),'ip'+str(i))['status']
            except Rejected as e: return e.code
        with ThreadPoolExecutor(max_workers=100) as pool:
            result=list(pool.map(call,range(1000)))
        self.assertEqual(result.count('ORDER_CREATED'),100)
        self.assertEqual(result.count('SOLD_OUT'),900)
        self.assertEqual(self.sale.stats()['stock'],0)
        self.assertTrue(self.sale.stats()['invariant_ok'])
        print('\n1000 requests / 100 concurrent workers: 100 orders, 900 sold out, stock=0')
    def test_random_queue_and_duplicate_join(self):
        sessions=[self.participant(i) for i in range(1000)]
        self.sale.join(sessions[0],'ip0')
        self.assertEqual(self.sale.draw(),{'registered':1000,'selected':100})
        self.assertEqual(sum(self.sale.ticket(s)['status']=='SELECTED' for s in sessions),100)
    def test_concurrent_retries(self):
        token=self.participant(1);self.sale.draw();ticket=self.sale.ticket(token)['ticket']
        def call(_):
            try:return self.sale.buy(token,ticket,'same-key','ip1')
            except Rejected as e:return {'error':e.code}
        with ThreadPoolExecutor(max_workers=50) as pool: results=list(pool.map(call,range(100)))
        ids={r['order_id'] for r in results if 'order_id' in r}
        self.assertEqual(len(ids),1);self.assertEqual(self.sale.stats()['orders'],1)
        self.assertEqual(self.sale.stats()['stock'],99)
        self.assertTrue(self.sale.buy(token,ticket,'same-key','ip1')['replayed'])
    def test_bot_and_forged_ticket(self):
        a=self.sale.session('a','same');b=self.sale.session('b','same');c=self.sale.session('c','same')
        self.sale.join(a,'ip');self.sale.join(b,'ip')
        with self.assertRaises(Rejected) as e:self.sale.join(c,'ip')
        self.assertEqual(e.exception.code,'DEVICE_ACCOUNT_LIMIT')
        self.sale.draw();ticket=self.sale.ticket(a)['ticket']
        for bad in ['fake',ticket+'x']:
            with self.assertRaises(Rejected):self.sale.buy(a,bad,'k','ip')
        with self.assertRaises(Rejected):self.sale.buy(b,ticket,'k','ip')
        for _ in range(5):self.sale.limit(('bot','ip'),5)
        with self.assertRaises(Rejected) as e:self.sale.limit(('bot','ip'),5)
        self.assertEqual(e.exception.status,429)
    def test_rollback_when_insert_fails(self):
        s=self.participant(1);self.sale.draw();t=self.sale.ticket(s)['ticket']
        with closing(self.sale.connect()) as db:
            db.execute("CREATE TRIGGER fail BEFORE INSERT ON orders BEGIN SELECT RAISE(ABORT,'injected failure'); END")
        with self.assertRaises(Exception):self.sale.buy(s,t,'k','ip')
        self.assertEqual(self.sale.stats()['stock'],100)
        self.assertEqual(self.sale.stats()['orders'],0)
    def test_restart_and_key_conflict(self):
        a=self.participant(1);b=self.participant(2);self.sale.draw()
        self.sale.buy(a,self.sale.ticket(a)['ticket'],'shared','ip1')
        with self.assertRaises(Rejected):self.sale.buy(b,self.sale.ticket(b)['ticket'],'shared','ip2')
        restarted=Sale(self.sale.path)
        self.assertEqual(restarted.stats()['orders'],1)
        self.assertEqual(restarted.stats()['stock'],99)
    def test_draw_respects_remaining_stock_after_restart(self):
        first=self.participant(1);self.sale.draw()
        self.sale.buy(first,self.sale.ticket(first)['ticket'],'first-order','ip1')
        restarted=Sale(self.sale.path)
        sessions=[]
        for i in range(2,102):
            token=restarted.session(f'u{i}',f'd{i}')
            restarted.join(token,f'ip{i}')
            sessions.append(token)
        self.assertEqual(restarted.draw(),{'registered':100,'selected':99})
        self.assertEqual(sum(restarted.ticket(s)['status']=='SELECTED' for s in sessions),99)
    def test_rejects_non_string_identity_and_ticket(self):
        with self.assertRaises(Rejected) as e:self.sale.session(['user'],'device')
        self.assertEqual(e.exception.code,'INVALID_IDENTITY')
        token=self.participant(1);self.sale.draw()
        with self.assertRaises(Rejected) as e:self.sale.buy(token,None,'key','ip1')
        self.assertEqual(e.exception.code,'INVALID_TICKET')
if __name__=='__main__':unittest.main(verbosity=2)
