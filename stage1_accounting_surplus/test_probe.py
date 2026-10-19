import unittest
from stage1_accounting_surplus.probe import (
  FACTORIES,TOK,PAIRS,BENTO,SNAPSHOT_OFFSETS,RUN_CAP_RU,
  selector,word,encode,unpack,toaddr,ETH,BASE,MAX_SKIM_SIMULATIONS
)
class TestAccounting(unittest.TestCase):
 def test_official_factories_and_box_addresses(self):
  self.assertEqual(FACTORIES[ETH]["UniswapV2"].lower(),"0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f")
  self.assertEqual(FACTORIES[BASE]["UniswapV2"].lower(),"0x8909dc15e40173ff4699343b6eb8132c65e18ec6")
  self.assertEqual(BENTO.lower(),"0xf5bce5077908a1b7370b9ae04adc565ebd643966")
 def test_known_abi_word_layouts(self):
  self.assertEqual(selector("balanceOf(address)"),"0x70a08231")
  self.assertEqual(selector("getReserves()"),"0x0902f1ac")
  self.assertEqual(selector("decimals()"),"0x313ce567")
  self.assertEqual(selector("skim(address)"),"0xbc25cf77")
  self.assertEqual(len(encode("getPair(address,address)",TOK[ETH]["USDC"][0],TOK[ETH]["WETH"][0])),138)
  self.assertEqual(unpack("0x"+word(3)+word(15),2),(3,15))
  self.assertEqual(toaddr(1),"0x"+"0"*39+"1")
 def test_immutable_cohorts_and_overshoot_budget(self):
  self.assertEqual(len(SNAPSHOT_OFFSETS),5)
  self.assertEqual(len(PAIRS[ETH]["UniswapV2"]),6)
  self.assertEqual(len(PAIRS[ETH]["SushiV2"]),4)
  self.assertEqual(len(PAIRS[BASE]["UniswapV2"]),3)
  self.assertLessEqual(RUN_CAP_RU,450)
  self.assertEqual(MAX_SKIM_SIMULATIONS,6)
 def test_money_and_decimals_not_conflated(self):
  self.assertEqual(TOK[ETH]["USDC"][1],6)
  self.assertEqual(TOK[ETH]["WETH"][1],18)
  self.assertEqual(TOK[ETH]["AMPL"][1],9)
  self.assertEqual(TOK[ETH]["stETH"][1],18)
if __name__=="__main__":unittest.main()
