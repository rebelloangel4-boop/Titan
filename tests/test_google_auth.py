import os,unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch,MagicMock
from titan import google_auth
from titan.providers import ProviderError,ConfigurationError
from titan.security import redact

class GoogleAuthTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'GOOGLE_REFRESH_TOKEN':'fixture-refresh','GOOGLE_CLIENT_ID':'fixture-client','GOOGLE_CLIENT_SECRET':'fixture-secret'},clear=True);self.env.start();google_auth._cache=None
 def tearDown(self):self.env.stop();google_auth._cache=None
 def test_concurrent_refresh_once(self):
  with patch.object(google_auth,'exchange',return_value=('fixture-access',3600)) as exchange:
   with ThreadPoolExecutor(max_workers=8) as pool:tokens=list(pool.map(lambda _:google_auth.access_token(),range(8)))
   self.assertEqual(tokens,['fixture-access']*8);self.assertEqual(exchange.call_count,1)
 def test_expiry_and_rotation(self):
  with patch.object(google_auth,'exchange',return_value=('fixture-access',60)) as exchange:
   google_auth.access_token();google_auth._cache=(google_auth._cache[0],'old',0);google_auth.access_token()
   os.environ['GOOGLE_REFRESH_TOKEN']='rotated';google_auth.access_token();self.assertEqual(exchange.call_count,3)
 def test_missing_config(self):
  del os.environ['GOOGLE_CLIENT_SECRET']
  with self.assertRaises(ConfigurationError):google_auth.access_token()
 def test_error_redaction(self):
  with patch.object(google_auth,'build_opener',side_effect=ValueError('fixture-secret')):
   with self.assertRaises(ProviderError) as caught:google_auth.exchange('x','fixture-secret','z')
   self.assertNotIn('fixture-secret',str(caught.exception))
  self.assertEqual(redact('fixture-secret fixture-refresh'),'[REDACTED] [REDACTED]')
 def test_exchange_form_and_validation(self):
  response=MagicMock();response.__enter__.return_value.read.return_value=b'{"access_token":"fixture-token","expires_in":3600,"token_type":"Bearer"}'
  opener=MagicMock();opener.open.return_value=response
  with patch.object(google_auth,'build_opener',return_value=opener):
   self.assertEqual(google_auth.exchange('a','b','c'),('fixture-token',3600))
   self.assertIn(b'grant_type=refresh_token',opener.open.call_args.args[0].data)
   response.__enter__.return_value.read.return_value=b'{"access_token":"x","expires_in":-1}'
   with self.assertRaises(ProviderError):google_auth.exchange('a','b','c')
