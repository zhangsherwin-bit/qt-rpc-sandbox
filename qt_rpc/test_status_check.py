"""Deterministic, offline classification of 403 response origins, no secrets."""
import unittest
from qt_rpc.status_check import classify

class FakeResponse:
    def __init__(self,status,body,headers=None,parsed=None):
        self.status_code=status
        self.text=body
        self.headers=headers or {}
        self._parsed=parsed
    def json(self):
        if self._parsed is None: raise ValueError("not json")
        return self._parsed

class TestStatusDiagnostic(unittest.TestCase):
    def test_cloudflare_1010_is_not_account_rejection(self):
        response=FakeResponse(
            403,"error code: 1010\n",{"Server":"cloudflare",
                  "CF-Ray":"a46e287cca7df85d-ORD"})
        result=classify(response)
        self.assertEqual(result["kind"],"CLOUDFLARE_1010_CLIENT_SIGNATURE_DENIAL")
        self.assertEqual(result["cf_ray"],"a46e287cca7df85d-ORD")
    def test_app_403_unverified_without_erroneous_cloudflare_claim(self):
        result=classify(FakeResponse(403,'{"error":"no subscription"}',
             {"Server":"cloudflare","Content-Type":"application/json"}))
        self.assertEqual(result["kind"],"STATUS_API_403_OR_UNCLASSIFIED_WAF")
        self.assertNotIn("response_body",result)
    def test_200_uses_allowlisted_fields_only(self):
        response=FakeResponse(200,"{}",{"Server":"cloudflare"},{
            "status":"active","rate_limit_rpm":300,"ru_budget":10000,
            "ru_remaining":9999,"is_exhausted":False,
            "key_prefix":"SENSITIVE_KEY_PREFIX",
            "email":"PRIVATE_EMAIL",
        })
        result=classify(response)
        self.assertEqual(result["kind"],"ACTIVE_KEY")
        self.assertEqual(result["rate_limit_rpm"],300)
        self.assertNotIn("SENSITIVE",str(result))
        self.assertNotIn("PRIVATE",str(result))
    def test_401_invalid_distinct_from_403(self):
        result=classify(FakeResponse(401,"Invalid credential"))
        self.assertEqual(result["kind"],"STATUS_API_401")
    def test_blocked_html_1020(self):
        result=classify(FakeResponse(403,"Error 1020: Access denied",
                                   {"Server":"cloudflare"}))
        self.assertEqual(result["kind"],"CLOUDFLARE_ACCESS_RULE_DENIAL")

if __name__=="__main__":unittest.main()
