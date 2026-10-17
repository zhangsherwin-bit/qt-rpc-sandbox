"""Pure validation and ranking for retrospective PegKeeper cohort trials."""

def validate_selection(selection):
    if selection.get('tokens_are_not_cash') is not True:
        raise ValueError('LP inventory cannot be called cash')
    cases=selection['cases']
    if len(cases)!=4 or len({x['date'] for x in cases})!=4:
        raise ValueError('four independent calendar dates required')
    txs={x['tx'].lower() for x in cases}
    if len(txs)!=4 or txs.intersection({x.lower() for x in selection['prior_excluded_txs']}):
        raise ValueError('duplicate or previously selected event')
    for c in cases:
        if not (isinstance(c['tx'],str) and c['tx'].startswith('0x') and len(c['tx'])==66 and all(x in '0123456789abcdef' for x in c['tx'][2:].lower())):
            raise ValueError('invalid transaction hash')
        if not c['reward_lp_raw'].isdigit() or int(c['reward_lp_raw'])<=0:
            raise ValueError('invalid reward units')
    return cases

def good_execution(row,weth='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'):
    return (row.get('status')=='0x1' and row.get('environment_verified') is True and
            row.get('prefix_exact_match') is True and len(row.get('rows',[]))==1 and
            row['rows'][0].get('cash_token','').lower()==weth)

def ranked_best(results,weth='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'):
    options=[]
    for mode,one in results:
        if good_execution(one,weth):
            amt=one['rows'][0].get('net_eth_after_base_fee_wei')
            if amt is not None:
                options.append((int(amt),-mode,mode))
    return max(options)[-1] if options else None
