import unittest, os, uuid
from unittest.mock import patch
import payment
class Test(unittest.TestCase):
 def test_gate(self):
  with patch.dict(os.environ, {'CATPDF_AUTO_RENEW_SANDBOX':'0'}):
   with self.assertRaises(payment.HTTPException) as e: payment.checkout(payment.CheckoutChoice(choice='monthly_myr_auto'),None)
   self.assertEqual(e.exception.status_code,503)
 def test_invoice(self):
  for choice in ('monthly_myr_auto','quarterly_usd_auto'):
   pid,cur,amount,months=payment.PRICES[choice]; uid=str(uuid.uuid4()); res=str(uuid.uuid4()); start=1700000000; end=start+months*30*86400
   inv=dict(id='in_test',livemode=False,status='paid',billing_reason='subscription_create',parent={'subscription_details':{'subscription':'sub_test'}},customer='cus_test',currency=cur,amount_paid=amount,amount_due=amount,lines={'data':[dict(pricing={'price_details':{'price':pid}},quantity=1,amount=amount,period={'start':start,'end':end})]})
   sub=dict(id='sub_test',livemode=False,customer='cus_test',metadata=dict(choice=choice,user_id=uid,reservation=res))
   with patch.object(payment,'stripe_get',side_effect=[inv,sub]),patch.object(payment,'payment_rpc',return_value={'activated':True}) as rpc:
    self.assertTrue(payment.fulfill_invoice('in_test')['activated']); self.assertEqual(rpc.call_args.args[1]['p_end'],end)
   inv['amount_paid']=0
   with patch.object(payment,'stripe_get',side_effect=[inv,sub]),patch.object(payment,'payment_rpc') as rpc:
    with self.assertRaises(ValueError): payment.fulfill_invoice('in_test')
    rpc.assert_not_called()
 def test_prices(self):
  self.assertEqual(len(payment.PRICES),10); self.assertEqual(sum(bool(p[3]) for p in payment.PRICES.values()),4)
if __name__=='__main__': unittest.main()
