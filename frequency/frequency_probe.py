"""Bounded small-ticket, three-calendar-day historical research. Never sends transactions."""
from pathlib import Path
import collections
import datetime as dt
import hashlib
import importlib.util
import json
import sys
import time
import traceback
import urllib.error
import urllib.request

OUT = Path('evidence')
RPC = 'https://rpc-eth.blockmachine.io'
SOURCE = 'https://raw.githubusercontent.com/zhangsherwin-bit/qt-rpc-sandbox/617c910731c6d0b0f76d23863389120358246b4e/direct_exit/run.py'
SOURCE_SHA = '4fc4e36cebafd8a921f5cabe82c2aec5c541288d422515b80a1e46bc15d0c75d'
HELPER_SHA = '26ddad1c60362ce288061c258445cee7b9cca55673926a6a60c37ae2809a5682'
RUNTIME_SHA = '15511d2f00b5c9b0bd03e4d12ea0373e4774ab2cd34df4ceb2df542264b58db6'
TOPIC = '0x143f1f8e861fbdeddd5b46e844b7d3ac7b86a122f36e8c463859ee6811b1f29c'
POOL = '0x4ebdf703948ddcea3b11f675b4d1fba9d2414a14'
DAYS = ('2026-09-02', '2026-09-09', '2026-09-16')
SIZES = (500, 2000)
THRESHOLD = 250 * 10**18
ALLOWED = {'eth_chainId', 'eth_getBlockByNumber', 'eth_getLogs', 'eth_getCode', 'eth_getTransactionReceipt', 'eth_simulateV1'}
MAX_REQUESTS = 200
MAX_SECONDS = 1100

def save(name, obj):
    p = OUT/name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding='utf-8')

def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def decode(log):
    if log.get('removed') or log.get('address', '').lower() != POOL or log.get('topics', [None])[0] != TOPIC:
        return None
    data = log.get('data', '')
    if not data.startswith('0x') or len(data) != 386:
        raise ValueError('Unsupported pool event layout')
    w = [int(data[i:i+64], 16) for i in range(2, len(data), 64)]
    return {'block': int(log['blockNumber'], 16), 'index': int(log['transactionIndex'], 16),
            'log_index': int(log['logIndex'], 16), 'hash': log['blockHash'], 'tx': log['transactionHash'],
            'sold_id': w[0], 'sold_raw': str(w[1]), 'bought_id': w[2], 'bought_raw': str(w[3]),
            'timestamp': int(log['blockTimestamp'], 16) if log.get('blockTimestamp') else None}

def choose(rows, noon):
    # First eligible canonical event after noon, not largest event or best quote.
    eligible = [r for r in rows if r['sold_id'] == 0 and r['bought_id'] == 1 and int(r['sold_raw']) >= THRESHOLD]
    eligible.sort(key=lambda r: (r['block'], r['index'], r['log_index']))
    selected = next((r for r in eligible if r['timestamp'] is not None and r['timestamp'] >= noon), None)
    return eligible, selected

class Client:
    def __init__(self):
        self.count = 0
        self.last = 0.0
        self.start = time.monotonic()
        self.stopped = False
    def rpc(self, name, method, params):
        if method not in ALLOWED:
            raise ValueError('Only fixed public read methods are permitted')
        if self.stopped or self.count >= MAX_REQUESTS or time.monotonic()-self.start > MAX_SECONDS:
            raise RuntimeError('Research budget/access stop')
        gap = 70 if method in ('eth_simulateV1', 'eth_getLogs') else 1
        time.sleep(max(0, gap-(time.monotonic()-self.last)))
        self.count += 1
        p = {'jsonrpc': '2.0', 'id': self.count, 'method': method, 'params': params}
        meta = {'name': name, 'url': RPC, 'payload': p, 'started_utc': utc()}
        body = b''
        result = None
        try:
            req = urllib.request.Request(RPC, json.dumps(p).encode(), {'Content-Type': 'application/json', 'User-Agent': 'QT-ReadOnly-Small-Ticket-Study/1'})
            with urllib.request.urlopen(req, timeout=55) as res:
                meta['http_status'] = res.status
                body = res.read(12000001)
            if len(body) > 12000000:
                raise ValueError('Response exceeds 12 MB bound')
            result = json.loads(body)
            meta['status'] = 'RPC_ERROR' if 'error' in result else 'OK'
            if 'error' in result and any(s in str(result['error']).lower() for s in ('rate limit', 'unauthorized', 'quota exceeded', 'api key required')):
                self.stopped = True
        except urllib.error.HTTPError as e:
            body = e.read(100000)
            meta.update(http_status=e.code, status='HTTP_ERROR', error=str(e))
            if e.code in (401, 403, 429):
                self.stopped = True
        except Exception as e:
            meta.update(status='UNAVAILABLE', error=repr(e))
        self.last = time.monotonic()
        meta.update(completed_utc=utc(), sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
        (OUT/'raw').mkdir(parents=True, exist_ok=True)
        (OUT/'raw'/f'{self.count:04d}.body').write_bytes(body)
        save(f'raw/{self.count:04d}.json', meta)
        if self.stopped:
            raise RuntimeError('Provider access/rate refusal: stop, no alternate endpoint')
        return result
    def val(self, *args):
        r = self.rpc(*args)
        if not isinstance(r, dict) or 'error' in r or r.get('result') is None:
            raise ValueError('Read unavailable: '+str(r)[:500])
        return r['result']

def bootstrap():
    req = urllib.request.Request(SOURCE, headers={'User-Agent': 'QT-Pinned-ReadOnly-Source/1'})
    with urllib.request.urlopen(req, timeout=30) as r:
        b = r.read(80001)
    if hashlib.sha256(b).hexdigest() != SOURCE_SHA:
        raise ValueError('Pinned source mismatch')
    p = OUT/'frozen_direct.py'
    p.write_bytes(b)
    spec = importlib.util.spec_from_file_location('frozen_direct', p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hashlib.sha256(module.body).hexdigest() != HELPER_SHA:
        raise ValueError('Pinned underlying helper mismatch')
    module.m.build()
    runtime = module.compile_alt()
    if hashlib.sha256(bytes.fromhex(runtime[2:])).hexdigest() != RUNTIME_SHA:
        raise ValueError('Compiled research runtime changed')
    return module.m, runtime

def main():
    OUT.mkdir(exist_ok=True)
    plan = {'days_UTC': DAYS, 'selection': 'First >=250-crvUSD-to-WETH pool swap at or after 12:00 UTC in each entire calendar day; freeze all selections before any simulation',
            'rationale': 'New small-flow development hypothesis motivated by September 1 census; not a rescue or clean holdout for old >=5000 rule',
            'sizes_USDC': SIZES, 'snapshot': 'Canonical state after trigger block, exact following block header, no within-block front-running',
            'native_reserve': '1,000,000 times target base fee in wei (must cover measured trade gas)',
            'min_payout_raw_USDC': 1, 'competitive_bid': 'zero; not a measured winning bid',
            'sampling': 'Six reset-state simulations in at most three separate days; not full-day profit census; sizes not additive',
            'pool': POOL, 'source_sha256': SOURCE_SHA, 'helper_sha256': HELPER_SHA, 'runtime_sha256': RUNTIME_SHA,
            'request_cap': MAX_REQUESTS, 'time_cap_seconds': MAX_SECONDS, 'no_keys_signing_broadcast': True,
            'no_production_balance_storage_or_oracle_overrides': True, 'reserved_Oct3_Oct9_untouched': True}
    save('PLAN.json', plan)
    out = {'plan': plan, 'started_utc': utc(), 'days': [], 'cases': [], 'transactions_sent': 0,
           'new_workflow_execution': True, 'actual_capture_measured': False}
    c = Client()
    try:
        m, runtime = bootstrap()
        m.rpc = c.rpc
        m.val = c.val
        m.MINIMUM = 1
        assert c.val('chain', 'eth_chainId', []) == '0x1'
        headers = {}
        def header(n):
            if n not in headers:
                headers[n] = c.val('header_'+str(n), 'eth_getBlockByNumber', [hex(n), False])
                assert int(headers[n]['number'], 16) == n
            return headers[n]
        anchor = 25878705
        anchor_time = 1788220800
        def lower(ts):
            estimate = anchor+(ts-anchor_time)//12
            lo, hi = estimate-2500, estimate+2500
            assert int(header(lo)['timestamp'], 16) < ts <= int(header(hi)['timestamp'], 16)
            while hi-lo > 1:
                mid = (hi+lo)//2
                if int(header(mid)['timestamp'], 16) < ts:
                    lo = mid
                else:
                    hi = mid
            return hi
        for day in DAYS:
            start = int(dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc).timestamp())
            a, end = lower(start), lower(start+86400)
            assert 0 < end-a <= 10000
            logs = c.val('logs_'+day, 'eth_getLogs', [{'address': POOL, 'fromBlock': hex(a), 'toBlock': hex(end-1), 'topics': [TOPIC]}])
            ids = [(l['transactionHash'], l['logIndex']) for l in logs]
            assert len(ids) == len(set(ids))
            rows = []
            for log in logs:
                r = decode(log)
                assert r is not None and a <= r['block'] < end
                if r['timestamp'] is None:
                    r['timestamp'] = int(header(r['block'])['timestamp'], 16)
                assert start <= r['timestamp'] < start+86400
                rows.append(r)
            eligible, pick = choose(rows, start+43200)
            record = {'day': day, 'block_from': a, 'block_to': end-1, 'all_swap_logs': len(rows),
                      'direction_counts': dict(collections.Counter(f"{r['sold_id']}->{r['bought_id']}" for r in rows)),
                      'qualifying_logs': len(eligible), 'qualifying_transactions': len(set(r['tx'] for r in eligible)),
                      'qualifying_blocks': len(set(r['block'] for r in eligible)), 'selected': pick,
                      'unquoted_qualifying_logs': len(eligible)-(1 if pick else 0)}
            save('days/'+day+'.json', {'summary': record, 'events': rows})
            out['days'].append(record)
        save('SELECTED_BEFORE_SIMULATIONS.json', out)
        for day in out['days']:
            pick = day['selected']
            if not pick:
                continue
            h = header(pick['block'])
            assert h['hash'] == pick['hash']
            receipt = c.val('trigger_receipt_'+day['day'], 'eth_getTransactionReceipt', [pick['tx']])
            assert receipt['status'] == '0x1' and receipt['blockHash'] == h['hash']
            assert any(l['address'].lower() == POOL and int(l['logIndex'], 16) == pick['log_index'] for l in receipt['logs'])
            save('triggers/'+day['day']+'.json', {'receipt': receipt, 'header': h})
            for name, addr in [('probe', m.PROBE), ('caller', m.CALLER)]:
                assert c.val(name+'_code_'+day['day'], 'eth_getCode', [addr, h['number']]) == '0x'
            target = header(pick['block']+1)
            m.RESERVE = max(1, int(target['baseFeePerGas'], 16)*1000000)
            seed = dict(pick, label='small_flow_'+day['day'])
            for amount in SIZES:
                case = m.simulate(seed, 1, amount, runtime, headers)
                case['reserve_budget_wei'] = str(m.RESERVE)
                case['trigger_crv_sold_raw'] = pick['sold_raw']
                case['trigger_day'] = day['day']
                out['cases'].append(case)
                save('SUMMARY.json', out)
                print(json.dumps({k:v for k,v in case.items() if k not in ('parent','target','response')}, indent=2), flush=True)
        save('headers.json', headers)
    except Exception as e:
        out.update(exception=repr(e), traceback=traceback.format_exc())
    out.update(completed_utc=utc(), rpc_requests=c.count, provider_stop=c.stopped)
    save('SUMMARY.json', out)
    print(json.dumps({'case_count':len(out['cases']), 'days':out['days'], 'exception':out.get('exception'), 'rpc_requests':c.count}, indent=2), flush=True)

def tests():
    import unittest
    class Checks(unittest.TestCase):
        def row(self, sold=THRESHOLD, second=43200):
            return {'block':1,'index':0,'log_index':0,'tx':'x','sold_id':0,'bought_id':1,'sold_raw':str(sold),'timestamp':second}
        def test_sizing_pair_is_fixed(self):
            self.assertEqual(SIZES,(500,2000))
        def test_boundary(self):
            rows=[self.row(THRESHOLD-1),self.row(THRESHOLD)]
            eligible,pick=choose(rows,43200)
            self.assertEqual(len(eligible),1);self.assertIsNotNone(pick)
        def test_no_pre_noon_pick(self):
            self.assertIsNone(choose([self.row(second=43199)],43200)[1])
        def test_wrong_direction(self):
            r=self.row();r['bought_id']=2
            self.assertEqual(choose([r],43200),([],None))
        def test_no_missing_timestamp_guess(self):
            r=self.row();r['timestamp']=None
            self.assertIsNone(choose([r],43200)[1])
        def test_method_allowlist(self):
            with self.assertRaises(ValueError):Client().rpc('x','eth_sendRawTransaction',[])
        def test_stopped_client(self):
            c=Client();c.stopped=True
            with self.assertRaises(RuntimeError):c.rpc('x','eth_chainId',[])
        def test_malformed_log(self):
            with self.assertRaises(ValueError):decode({'address':POOL,'topics':[TOPIC],'data':'0x00'})
    if not unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks)).wasSuccessful():
        raise SystemExit(1)

if __name__ == '__main__':
    tests() if '--self-test' in sys.argv else main()
