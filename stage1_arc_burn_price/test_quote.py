import unittest
from decimal import Decimal
from Crypto.Hash import keccak
from stage1_arc_burn_price.quote import (
  BURN_TOKEN,BURN_SIZE,CASH,ORIGINAL_GAS,OUTPUT_QUANTITIES,
  PARENT,TARGET,QUOTER,POSITION_MANAGER,MAX_REQUESTS,
  poolkey_decode,encode_exact_output,parse_quote,sig,word
)
def pool():
 return {"currency0":"0x"+"0"*40,"currency1":BURN_TOKEN,
          "fee":3000,"tickSpacing":60,"hooks":"0x"+"0"*40,
          "positionInfo_raw":"0"*64}
class TestArcBurnPrice(unittest.TestCase):
 def test_break_even_in_native_usdc(self):
  self.assertEqual(CASH-ORIGINAL_GAS,9478540300000000000)
  self.assertEqual((Decimal(CASH-ORIGINAL_GAS)/Decimal(BURN_SIZE)),
                   Decimal("0.0000189570806"))
  self.assertEqual(MAX_REQUESTS,14)
 def test_decode_source_v4_position_pool(self):
  p=pool();parts=[int(p["currency0"],16),int(p["currency1"],16),
      3000,60,0,17]
  x=poolkey_decode("0x"+"".join(word(z) for z in parts))
  self.assertEqual(x["fee"],3000)
  self.assertEqual(x["currency1"],BURN_TOKEN)
  self.assertEqual(x["positionInfo_raw"],word(17))
 def test_reject_invalid_position_pair_no_fake_conversions(self):
  p=pool();p["currency1"]="0x"+"11"*20
  with self.assertRaises(ValueError):encode_exact_output(p,BURN_SIZE)
  p=pool();p["currency0"]="0x"+"22"*20
  with self.assertRaises(ValueError):encode_exact_output(p,BURN_SIZE)
 def test_abi_tuple_offset_and_static_words(self):
  p=pool()
  data=encode_exact_output(p,BURN_SIZE)
  self.assertEqual(data[:10],sig("quoteExactOutputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))"))
  raw=data[10:]
  self.assertEqual(len(raw),64*10)
  words=[raw[i*64:(i+1)*64] for i in range(10)]
  self.assertEqual(int(words[0],16),32)
  self.assertEqual(int(words[2],16),int(BURN_TOKEN,16))
  self.assertEqual(int(words[6],16),1)
  self.assertEqual(int(words[7],16),BURN_SIZE)
  self.assertEqual(int(words[8],16),8*32)
  self.assertEqual(int(words[9],16),0)
 def test_quote_preserves_exact_decimal(self):
  got=parse_quote("0x"+word(9300000000000000000)+word(140000),BURN_SIZE)
  self.assertEqual(Decimal(got["usdc_per_token_for_this_quantity"]),Decimal("0.0000186"))
  self.assertEqual(got["required_input_native_USDC_raw"],"9300000000000000000")
  self.assertEqual(got["quoter_estimated_simulation_gas_not_execution_cost"],140000)
 def test_failed_or_zero_quote_no_positive_inference(self):
  with self.assertRaises(ValueError):parse_quote("0x"+word(0)+word(33000),BURN_SIZE)
  with self.assertRaises(ValueError):parse_quote("0x",BURN_SIZE)
 def test_small_sizes_are_not_equal_to_full_burn(self):
  self.assertEqual(OUTPUT_QUANTITIES,[5000*10**18,50000*10**18,500000*10**18])
  self.assertEqual(TARGET-PARENT,1)
if __name__=="__main__":unittest.main()
