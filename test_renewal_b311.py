import unittest, io, contextlib, os
from unittest.mock import patch
from urllib.error import HTTPError
from fastapi import HTTPException
import payment
class DiagnosticTests(unittest.TestCase):
 def test_stages(self):
  for stage in ('supabase_read','stripe_read'):
   with self.subTest(stage=stage), patch.dict(os.environ,{'STRIPE_SECRET_KEY':'sk_test_mock'}), patch.object(payment,'renewal_record',return_value={'subscription_id':'sub_test'}) as db, patch.object(payment,'stripe_get') as stripe:
    error=HTTPError('https://secret.invalid/token',403,'SECRET',None,None)
    (db if stage=='supabase_read' else stripe).side_effect=error
    out=io.StringIO()
    with contextlib.redirect_stdout(out), self.assertRaises(HTTPException) as exc: payment.renewal_operation('test')
    self.assertEqual(exc.exception.status_code,503)
    self.assertIn(stage,out.getvalue());self.assertIn('403',out.getvalue());self.assertNotIn('SECRET',out.getvalue());self.assertNotIn('secret.invalid',out.getvalue())
    if stage=='supabase_read': stripe.assert_not_called()
if __name__=='__main__': unittest.main()
