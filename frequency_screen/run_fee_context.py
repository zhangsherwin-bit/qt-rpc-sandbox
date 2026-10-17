"""Re-run the frozen study with explicit historical gasPrice, not a state override.

The prior calls returned the right chain/block/time but BASEFEE=0. Keep every
original environment check. This wrapper changes only the eth_call envelope;
no sender balances, production storage, oracles, times or block headers change.
No transaction signing or submission. Unavailable observations stay unavailable.
"""
import copy
import json
from pathlib import Path
import run_study as study

ORIGINAL = study.Client.val
HEADERS = {}
OBSERVATIONS = []

def corrected_val(self, name, method, params):
    p = copy.deepcopy(params)
    if method == 'eth_call' and len(p) >= 3 and isinstance(p[0], dict) and p[0].get('to', '').lower() == study.QUOTE.lower():
        h = HEADERS.get(p[1])
        if h is None:
            raise ValueError('No canonical header for explicit quote gas price')
        p[0]['gasPrice'] = hex(max(1, int(h['baseFeePerGas'], 16)))
    result = ORIGINAL(self, name, method, p)
    if method == 'eth_getBlockByNumber' and isinstance(result, dict):
        HEADERS[result['number']] = result
    if method == 'eth_call' and p[0].get('to', '').lower() == study.QUOTE.lower():
        obs = {'name': name, 'gasPrice': p[0].get('gasPrice'), 'actual_context': study.words(result, 260)[:4],
               'expected_context': [1, int(h['number'], 16), int(h['timestamp'], 16), int(h['baseFeePerGas'], 16)]}
        OBSERVATIONS.append(obs)
        study.save('FEE_CONTEXT_CONTROLS.json', OBSERVATIONS)
        if obs['actual_context'] != obs['expected_context']:
            self.stop = True
            raise ValueError('Corrected call still has wrong context; abort, do not weaken check')
    return result

if __name__ == '__main__':
    study.Client.val = corrected_val
    study.run()
    study.save('ENVELOPE_CHANGE.json', {'change': 'explicit gasPrice on quotation eth_call only',
      'original_core_source_unchanged': True, 'original_21_states_unchanged': True,
      'original_32_quotes_per_state_unchanged': True, 'context_validation_retained': True,
      'transactions_sent': 0})
