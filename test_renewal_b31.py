import unittest, os
from unittest.mock import patch, MagicMock
import payment
from fastapi import HTTPException
class RenewalTests(unittest.TestCase):
 def setUp(self):
  self.uid='test-user'; self.record={'subscription_id':'sub_test','plan':'monthly','currency':'myr','paid_until':'2027-02-28'}
  self.sub={'id':'sub_test','livemode':False,'metadata':{'user_id':self.uid,'choice':'monthly_myr_auto'},'status':'active','cancel_at_period_end':False,'cancel_at':None}
  for p in [patch.dict(os.environ,{'STRIPE_SECRET_KEY':'sk_test_mock'}),patch.object(payment,'renewal_record',return_value=self.record),patch.object(payment,'stripe_get',return_value=self.sub),patch.object(payment.urllib.request,'urlopen',return_value=MagicMock())]:
   p.start();self.addCleanup(p.stop)
 def test_read(self): self.assertFalse(payment.renewal_operation(self.uid)['subscription']['cancel_at_period_end'])
 def test_cancel(self):
  payment.stripe_get.side_effect=[self.sub,{**self.sub,'cancel_at_period_end':True}];self.assertTrue(payment.renewal_operation(self.uid,True)['subscription']['cancel_at_period_end'])
 def test_resume(self):
  payment.stripe_get.side_effect=[{**self.sub,'cancel_at_period_end':True},self.sub];self.assertFalse(payment.renewal_operation(self.uid,False)['subscription']['cancel_at_period_end'])
 def test_noop(self):
  payment.renewal_operation(self.uid,False);payment.urllib.request.urlopen.assert_not_called()
 def test_owner(self):
  with self.assertRaises(HTTPException):payment.renewal_operation('other',True)
  payment.urllib.request.urlopen.assert_not_called()
 def test_live(self):
  self.sub['livemode']=True
  with self.assertRaises(HTTPException):payment.renewal_operation(self.uid,True)
 def test_manual(self):
  payment.renewal_record.return_value=None
  self.assertIsNone(payment.renewal_operation(self.uid)['subscription'])
  with self.assertRaises(HTTPException):payment.renewal_operation(self.uid,True)
 def test_unconfirmed(self):
  with self.assertRaises(HTTPException):payment.renewal_operation(self.uid,True)
 def test_terminal(self):
  self.sub['status']='canceled'
  with self.assertRaises(HTTPException):payment.renewal_operation(self.uid,True)
if __name__=='__main__':unittest.main()
