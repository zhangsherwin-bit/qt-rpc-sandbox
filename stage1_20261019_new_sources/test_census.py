"""Offline contract-event parser and economic-gate controls, no network calls."""
import unittest
from unittest.mock import patch
from stage1_20261019_new_sources.census import (
    FILL_TOPIC, AA_TOPIC, TRANSFER_TOPIC, HANDLE_OPS_V7_SELECTOR,
    parse_fill,parse_aa,token_deltas,beneficiary_from_tx,sample_windows,
    REQUIRED_CHAINS, MAX_RECEIPT_TX_PER_FAMILY_CHAIN)

def word(n):return hex(n)[2:].zfill(64)
def topic_address(a):return "0x"+a[2:].zfill(64)

class TestFrozen(unittest.TestCase):
 def test_sources_are_chain_specific(self):
  self.assertEqual(len(REQUIRED_CHAINS),2)
  for ch,inventory in REQUIRED_CHAINS.items():
   self.assertEqual(len(inventory["entrypoints"]),2)
   self.assertEqual(len(inventory["uniswapx"]),2)
   for a in list(inventory["entrypoints"].values())+list(inventory["uniswapx"].values()):
    self.assertEqual(len(a),42)
 def test_windows_frozen_disjoint_and_unselected(self):
  rows=sample_windows(999999)
  self.assertEqual(len(rows),5)
  for v in rows:self.assertEqual(v["end"]-v["start"]+1,360)
  for a,b in zip(rows,rows[1:]):self.assertGreater(a["start"],b["end"])
 def test_uniswap_fill_exact_abi(self):
  filler="0x"+"12"*20
  swapper="0x"+"13"*20
  r=parse_fill({"topics":[FILL_TOPIC,"0x"+"ab"*32,topic_address(filler),
     topic_address(swapper)],"data":"0x"+word(31),"address":REQUIRED_CHAINS[8453]["uniswapx"]["dutch_v3"],
     "transactionHash":"0x"+"33"*32,"blockNumber":"0xf","logIndex":"0x5"},8453)
  self.assertEqual(r["filler"],filler)
  self.assertEqual(r["nonce"],31)
  self.assertEqual(r["reactor_type"],"dutch_v3")
  with self.assertRaises(ValueError):
   parse_fill({"topics":[],"data":"0x"},8453)
 def test_erc4337_paid_fee_not_assumed_profit(self):
  r=parse_aa({"topics":[AA_TOPIC,"0x"+"bb"*32,topic_address("0x"+"21"*20),
      topic_address("0x"+"00"*20)],
     "data":"0x"+word(7)+word(1)+word(15304000)+word(630000),
     "address":REQUIRED_CHAINS[1]["entrypoints"]["v0.7"],
     "transactionHash":"0x"+"41"*32,"blockNumber":"0x29","logIndex":"0x0"},1)
  self.assertEqual(r["actual_gas_cost_wei"],15304000)
  self.assertEqual(r["actual_gas_used"],630000)
  self.assertEqual(r["entrypoint_version"],"v0.7")
 def test_transfer_deltas_accurately_net_wei(self):
  filler="0x"+"42"*20;third="0x"+"73"*20
  transfer=lambda a,b,v:{"topics":[TRANSFER_TOPIC,topic_address(a),topic_address(b)],
                            "data":"0x"+word(v),"address":"0x"+"77"*20}
  result=token_deltas({"logs":[transfer(third,filler,300),
           transfer(filler,third,220)]},filler)
  self.assertEqual(result["0x"+"77"*20],"80")
 def test_beneficiary_recovered_from_handleops_header(self):
  b="0x"+"fa"*20
  head=HANDLE_OPS_V7_SELECTOR+word(64)+word(int(b,16))
  self.assertEqual(beneficiary_from_tx({"input":head}),b)
  self.assertIsNone(beneficiary_from_tx({"input":"0x12345678"}))
  self.assertEqual(MAX_RECEIPT_TX_PER_FAMILY_CHAIN,8)
if __name__=="__main__":unittest.main()
