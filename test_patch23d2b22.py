import unittest, os
from unittest.mock import patch, MagicMock
import payment
class Recovery(unittest.TestCase):
 def test_expire_verified(self):
  for status,paid,ok in [('expired','unpaid',True),('complete','paid',False),('open','unpaid',False),('expired','paid',False)]:
   old=dict(id='cs_test_example',livemode=False,client_reference_id='u',metadata={'user_id':'u'},status=status,payment_status=paid)
   with patch.dict(os.environ,{'STRIPE_SECRET_KEY':'sk_test_mock'}),patch.object(payment.urllib.request,'urlopen',side_effect=TimeoutError),patch.object(payment,'stripe_get',return_value=old):
    if ok: self.assertEqual(payment.expire_checkout('cs_test_example','u'),old)
    else:
     with self.assertRaises(payment.HTTPException): payment.expire_checkout('cs_test_example','u')
 def test_wrong_owner(self):
  with patch.dict(os.environ,{'STRIPE_SECRET_KEY':'sk_test_mock'}),patch.object(payment.urllib.request,'urlopen',side_effect=TimeoutError),patch.object(payment,'stripe_get',return_value={'id':'cs_test_example','livemode':False,'client_reference_id':'other'}):
   with self.assertRaises(payment.HTTPException): payment.expire_checkout('cs_test_example','u')
if __name__=='__main__': unittest.main()
