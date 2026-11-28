"""Sandbox manual and recurring payment fulfillment."""
import os, json, urllib.request, urllib.parse, urllib.error, base64, asyncio, uuid
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
router = APIRouter()
PRICES = {
 'daily_myr_manual': ('price_1UgJSjPQONraeaKvSQyVF8uh','myr',790,0),
 'daily_usd_manual': ('price_1UgJWePQONraeaKvkrV2ply0','usd',199,0),
 'monthly_myr_auto': ('price_1UgJZtPQONraeaKvFSFx0Sfr','myr',3590,1),
 'monthly_usd_auto': ('price_1UgJcKPQONraeaKvg9GehsYS','usd',899,1),
 'monthly_myr_manual': ('price_1UgJjlPQONraeaKvdxg9glPs','myr',3590,0),
 'monthly_usd_manual': ('price_1UgJjlPQONraeaKv0QPferT2','usd',899,0),
 'quarterly_myr_auto': ('price_1UgJmyPQONraeaKvx27uTfGj','myr',9690,3),
 'quarterly_usd_auto': ('price_1UgJmyPQONraeaKvMK1javCu','usd',2429,3),
 'quarterly_myr_manual': ('price_1UgJmyPQONraeaKv6RvI30QX','myr',9690,0),
 'quarterly_usd_manual': ('price_1UgJmyPQONraeaKvCaFPBuaD','usd',2429,0),
}
def validate_price(p, expected):
    pid,currency,amount,months=expected
    recurring=p.get('recurring') or {}
    return (p.get('id')==pid and p.get('livemode') is False and p.get('active') is True and p.get('currency')==currency and p.get('unit_amount')==amount and p.get('billing_scheme')=='per_unit' and (p.get('type')=='recurring' and recurring.get('interval')=='month' and recurring.get('interval_count')==months if months else p.get('type')=='one_time' and not recurring))
def verify():
    key=os.environ.get('STRIPE_SECRET_KEY','')
    if not key.startswith('sk_test_'): raise HTTPException(503,'Sandbox secret key missing or invalid')
    auth=base64.b64encode((key+':').encode()).decode()
    results={}
    for name,expected in PRICES.items():
        try:
            req=urllib.request.Request('https://api.stripe.com/v1/prices/'+expected[0],headers={'Authorization':'Basic '+auth})
            with urllib.request.urlopen(req,timeout=8) as response: p=json.load(response)
            results[name]='ok' if validate_price(p,expected) else 'mismatch'
        except Exception: results[name]='unverified'
    return {'sandbox':True,'checkout_enabled':True,'all_verified':all(v=='ok' for v in results.values()),'prices':results}
# Verification is opt-in from server startup configuration, not a public API.
@router.get('/payments/status')
def status():
    return {'sandbox':True,'checkout_enabled':True,'price_verification':'see Render startup logs','auto_renew_enabled':os.getenv('CATPDF_AUTO_RENEW_SANDBOX') == '1' and os.getenv('STRIPE_SECRET_KEY','').startswith('sk_test_')}
async def startup_verify():
    try:
        result=await asyncio.to_thread(verify)
        print('CatPDF Stripe sandbox verification:',json.dumps(result),flush=True)
    except HTTPException as e:
        print('CatPDF Stripe sandbox verification:',e.detail,flush=True)


class CheckoutChoice(BaseModel):
    choice: str
    replace_session: str | None = None

@router.post('/payments/checkout')
def checkout(body: CheckoutChoice, request: Request):
    expected = PRICES.get(body.choice)
    if expected is None: raise HTTPException(400, 'Unknown plan')
    if expected[3] and os.getenv('CATPDF_AUTO_RENEW_SANDBOX') != '1': raise HTTPException(503, 'Automatic renewal is temporarily unavailable')
    if not os.environ.get('STRIPE_WEBHOOK_SECRET') or not os.environ.get('SUPABASE_SERVICE_ROLE_KEY'): raise HTTPException(503, 'Payment fulfillment is not configured')
    key = os.environ.get('STRIPE_SECRET_KEY', '')
    if not key.startswith('sk_test_'): raise HTTPException(503, 'Sandbox unavailable')
    token = request.headers.get('authorization', '')
    if not token.startswith('Bearer '): raise HTTPException(401, 'Login required')
    try:
        req = urllib.request.Request('https://unauvicwfjnfqyrtexhy.supabase.co/auth/v1/user', headers={'apikey':'sb_publishable_y9pVKZ47UfWibxYaoOcoAg_3mlqpDPs','Authorization':token})
        with urllib.request.urlopen(req, timeout=10) as r: user=json.load(r)
        uid=str(uuid.UUID(user['id']))
    except Exception: raise HTTPException(401, 'Unable to verify account') from None
    reservation = str(uuid.uuid4())
    try:
        existing = payment_rpc('catpdf_checkout_pending', {'p_user':uid})
        if existing:
            old = stripe_get('checkout/sessions/'+urllib.parse.quote(existing,safe=''))
            meta = old.get('metadata') or {}
            if (old.get('id') != existing or old.get('livemode') is not False
                    or old.get('client_reference_id') != uid or meta.get('user_id') != uid):
                raise HTTPException(503, 'Unable to verify existing checkout')
            if body.replace_session and body.replace_session != existing:
                raise HTTPException(409, 'Checkout changed; select your plan again')
            if old.get('status') == 'open':
                if old.get('payment_status') != 'unpaid':
                    raise HTTPException(409, 'Payment requires reconciliation')
                if meta.get('choice') != body.choice:
                    if body.replace_session != existing:
                        raise HTTPException(409, {'code':'checkout_conflict','session':existing,'choice':meta.get('choice')})
                    old = expire_checkout(existing, uid)
                else:
                    target = old.get('url') or ''
                    if urllib.parse.urlparse(target).netloc != 'checkout.stripe.com' or not target.startswith('https://'):
                        raise HTTPException(503, 'Invalid sandbox session URL')
                    return {'url':target,'sandbox':True}
            if old.get('status') == 'expired' and old.get('payment_status') == 'unpaid':
                payment_rpc('catpdf_checkout_release', {'p_user':uid,'p_session':existing})
            else:
                raise HTTPException(409, 'Payment pending or completed; check dashboard')
        elif body.replace_session:
            raise HTTPException(409, 'Checkout changed; select your plan again')
        result = payment_rpc('catpdf_checkout_reserve', {'p_user':uid,'p_reservation':reservation})
        if not result.get('allowed'): raise HTTPException(409,result.get('reason','Checkout blocked'))
    except HTTPException: raise
    except Exception: raise HTTPException(503,'Unable to verify purchase eligibility') from None
    auth = 'Basic '+base64.b64encode((key+':').encode()).decode()
    submitted = False
    try:
        req=urllib.request.Request('https://api.stripe.com/v1/prices/'+expected[0],headers={'Authorization':auth})
        with urllib.request.urlopen(req,timeout=10) as r: price=json.load(r)
        if not validate_price(price,expected): raise HTTPException(503,'Price verification failed')
        site='https://razief12.github.io/CatPDF-Beta/'
        data={'mode':'subscription' if expected[3] else 'payment','line_items[0][price]':expected[0],'line_items[0][quantity]':'1','success_url':site+'?payment=test_success','cancel_url':site+'?payment=cancelled','client_reference_id':uid,'metadata[user_id]':uid,'metadata[choice]':body.choice,'metadata[reservation]':reservation,'allowed_payment_method_types[0]':'card','expires_at':str(int(time.time())+1860)}
        if expected[3]:
            data.update({'subscription_data[metadata][user_id]':uid,'subscription_data[metadata][choice]':body.choice,'subscription_data[metadata][reservation]':reservation})
        req=urllib.request.Request('https://api.stripe.com/v1/checkout/sessions',data=urllib.parse.urlencode(data).encode(),headers={'Authorization':auth,'Content-Type':'application/x-www-form-urlencoded','Idempotency-Key':reservation},method='POST')
        submitted = True
        with urllib.request.urlopen(req,timeout=15) as r: session=json.load(r)
        target=session.get('url','')
        if session.get('livemode') is not False or urllib.parse.urlparse(target).netloc!='checkout.stripe.com' or not target.startswith('https://'): raise HTTPException(503,'Invalid sandbox session')
        payment_rpc('catpdf_checkout_bind', {'p_user':uid,'p_reservation':reservation,'p_session':session['id']})
        return {'url':target,'sandbox':True}
    except Exception as exc:
        # Only release when no creation request was sent, or Stripe explicitly rejected it.
        if not submitted or (isinstance(exc, urllib.error.HTTPError) and exc.code == 400):
            try:
                payment_rpc('catpdf_checkout_abort', {'p_user':uid,'p_reservation':reservation})
            except Exception:
                print('CatPDF checkout reservation cleanup failed', flush=True)
        if isinstance(exc, HTTPException): raise
        raise HTTPException(502,'Unable to create sandbox checkout') from None

# Patch23C: one-off fulfillment only. Recurring checkout is paused until invoice lifecycle support.
import hashlib, hmac, time

def verify_signature(raw, header, secret, now=None):
    parts = [p.split('=', 1) for p in header.split(',') if '=' in p]
    timestamps = [v for k,v in parts if k == 't']
    if len(timestamps) != 1: return False
    try: timestamp = int(timestamps[0])
    except ValueError: return False
    if abs((time.time() if now is None else now)-timestamp)>300: return False
    digest=hmac.new(secret.encode(), timestamps[0].encode()+b'.'+raw, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(digest,v) for k,v in parts if k=='v1')

def stripe_get(path):
    key=os.environ['STRIPE_SECRET_KEY']
    if not key.startswith('sk_test_'): raise ValueError('Sandbox required')
    auth='Basic '+base64.b64encode((key+':').encode()).decode()
    with urllib.request.urlopen(urllib.request.Request('https://api.stripe.com/v1/'+path,headers={'Authorization':auth}),timeout=15) as r: return json.load(r)

def expire_checkout(session_id, uid):
    if not session_id.startswith('cs_test_'): raise ValueError('Sandbox required')
    key=os.environ['STRIPE_SECRET_KEY']
    if not key.startswith('sk_test_'): raise ValueError('Sandbox required')
    path='checkout/sessions/'+urllib.parse.quote(session_id,safe='')
    auth='Basic '+base64.b64encode((key+':').encode()).decode()
    try:
        req=urllib.request.Request('https://api.stripe.com/v1/'+path+'/expire',data=b'',headers={'Authorization':auth,'Idempotency-Key':'expire-'+session_id},method='POST')
        with urllib.request.urlopen(req,timeout=15) as r: json.load(r)
    except Exception:
        pass  # A timeout or race is resolved only by authoritative retrieval.
    old=stripe_get(path)
    if old.get('id')!=session_id or old.get('livemode') is not False or old.get('client_reference_id')!=uid or (old.get('metadata') or {}).get('user_id')!=uid:
        raise HTTPException(503,'Unable to verify checkout expiration')
    if old.get('status')!='expired' or old.get('payment_status')!='unpaid':
        raise HTTPException(409,'Checkout could not be cancelled safely; check dashboard')
    return old

def payment_rpc(name, data):
    key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
    req=urllib.request.Request('https://unauvicwfjnfqyrtexhy.supabase.co/rest/v1/rpc/'+name,data=json.dumps(data).encode(),headers={'apikey':key,'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=15) as r:
        raw = r.read()
        if not raw.strip():
            if name in ('catpdf_checkout_bind','catpdf_checkout_release','catpdf_checkout_abort','catpdf_checkout_pending'):
                return None
            raise ValueError('Unexpected empty RPC response')
        return json.loads(raw)

def fulfill_manual(session_id):
    if not session_id.startswith('cs_test_'): raise ValueError('Invalid session')
    s=stripe_get('checkout/sessions/'+urllib.parse.quote(session_id,safe=''))
    if s.get('livemode') is not False or s.get('mode')!='payment' or s.get('status')!='complete' or s.get('payment_status')!='paid': raise ValueError('Unpaid session')
    meta=s.get('metadata') or {}; choice=meta.get('choice'); expected=PRICES.get(choice)
    if not expected or expected[3]: raise ValueError('Invalid choice')
    uid=str(uuid.UUID(meta['user_id']))
    if s.get('client_reference_id')!=uid or s.get('currency')!=expected[1] or s.get('amount_total')!=expected[2]: raise ValueError('Session mismatch')
    lines=stripe_get('checkout/sessions/'+urllib.parse.quote(session_id,safe='')+'/line_items')
    items=lines.get('data',[])
    if lines.get('has_more') or len(items)!=1 or items[0].get('quantity')!=1 or (items[0].get('price') or {}).get('id')!=expected[0]: raise ValueError('Line item mismatch')
    intent=s.get('payment_intent')
    if not isinstance(intent,str) or not intent.startswith('pi_'): raise ValueError('Missing payment intent')
    pi=stripe_get('payment_intents/'+urllib.parse.quote(intent,safe=''))
    if pi.get('livemode') is not False or pi.get('status')!='succeeded' or pi.get('amount_received')!=expected[2] or pi.get('currency')!=expected[1]: raise ValueError('Payment mismatch')
    key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
    data={'p_session':session_id,'p_intent':intent,'p_user':uid,'p_plan':choice.split('_')[0],'p_amount':expected[2],'p_currency':expected[1],'p_reservation':meta.get('reservation')}
    req=urllib.request.Request('https://unauvicwfjnfqyrtexhy.supabase.co/rest/v1/rpc/catpdf_fulfill_manual_v3',data=json.dumps(data).encode(),headers={'apikey':key,'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=15) as r: return json.load(r)

@router.post('/payments/webhook')
async def webhook(request: Request):
    secret=os.environ.get('STRIPE_WEBHOOK_SECRET','')
    if not secret.startswith('whsec_') or not os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or not os.environ.get('STRIPE_SECRET_KEY','').startswith('sk_test_'): raise HTTPException(503,'Fulfillment not configured')
    raw=await request.body()
    if len(raw)>1024*1024 or not verify_signature(raw,request.headers.get('stripe-signature',''),secret): raise HTTPException(400,'Invalid signature')
    try: event=json.loads(raw)
    except ValueError: raise HTTPException(400,'Invalid event') from None
    if event.get('livemode') is not False: raise HTTPException(400,'Sandbox required')
    if event.get('type') == 'invoice.paid':
        try: await asyncio.to_thread(fulfill_invoice,event['data']['object']['id'])
        except Exception as e:
            print('CatPDF invoice fulfillment failed:',type(e).__name__,flush=True)
            raise HTTPException(503,'Invoice fulfillment failed; retry required') from None
        return {'received':True}
    if event.get('type') not in ('checkout.session.completed','checkout.session.async_payment_succeeded'): return {'received':True}
    s=event['data']['object']
    if s.get('mode')!='payment' or s.get('payment_status')!='paid': return {'received':True}
    try: await asyncio.to_thread(fulfill_manual,s['id'])
    except Exception as e:
        print('CatPDF fulfillment failed:',type(e).__name__,flush=True)
        raise HTTPException(503,'Fulfillment failed; retry required') from None
    return {'received':True}


def fulfill_invoice(invoice_id):
    if not isinstance(invoice_id,str) or not invoice_id.startswith('in_'): raise ValueError('Invalid invoice')
    inv=stripe_get('invoices/'+urllib.parse.quote(invoice_id,safe=''))
    if inv.get('id')!=invoice_id or inv.get('livemode') is not False or inv.get('status')!='paid' or inv.get('paid_out_of_band'): raise ValueError('Unverified invoice')
    if inv.get('billing_reason') not in ('subscription_create','subscription_cycle'): return {'ignored':True}
    parent=inv.get('parent') or {}
    sid=(parent.get('subscription_details') or {}).get('subscription') or inv.get('subscription')
    if not isinstance(sid,str) or not sid.startswith('sub_'): raise ValueError('Missing subscription')
    sub=stripe_get('subscriptions/'+urllib.parse.quote(sid,safe=''))
    meta=sub.get('metadata') or {}; choice=meta.get('choice'); expected=PRICES.get(choice)
    if not choice and not meta.get('user_id'): return {'ignored':True}
    if not expected or not expected[3] or sub.get('id')!=sid or sub.get('livemode') is not False or sub.get('customer')!=inv.get('customer'): raise ValueError('Subscription mismatch')
    uid=str(uuid.UUID(meta['user_id'])); reservation=str(uuid.UUID(meta['reservation']))
    if inv.get('currency')!=expected[1] or inv.get('amount_paid')!=expected[2] or inv.get('amount_due')!=expected[2]: raise ValueError('Invoice amount mismatch')
    lines=inv.get('lines') or {}; items=lines.get('data') or []
    if lines.get('has_more') or len(items)!=1: raise ValueError('Unexpected invoice lines')
    line=items[0]; price=((line.get('pricing') or {}).get('price_details') or {}).get('price') or (line.get('price') or {}).get('id')
    if price!=expected[0] or line.get('quantity')!=1 or line.get('amount')!=expected[2]: raise ValueError('Invoice line mismatch')
    period=line.get('period') or {}; start=int(period['start']); end=int(period['end'])
    if not 0<end-start<=100*86400: raise ValueError('Invalid billing period')
    return payment_rpc('catpdf_fulfill_invoice_v1',{'p_invoice':invoice_id,'p_subscription':sid,'p_user':uid,'p_reservation':reservation,'p_plan':choice.split('_')[0],'p_amount':expected[2],'p_currency':expected[1],'p_start':start,'p_end':end})

# B3.1: Stripe is authoritative for cancellation scheduling. Never mutate paid access.
class RenewalChoice(BaseModel):
    cancel_at_period_end: bool

def renewal_account(request):
    token=request.headers.get('authorization','')
    if not token.startswith('Bearer '): raise HTTPException(401,'Login required')
    try:
        req=urllib.request.Request('https://unauvicwfjnfqyrtexhy.supabase.co/auth/v1/user',headers={'apikey':'sb_publishable_y9pVKZ47UfWibxYaoOcoAg_3mlqpDPs','Authorization':token})
        with urllib.request.urlopen(req,timeout=10) as r: return str(uuid.UUID(json.load(r)['id']))
    except Exception: raise HTTPException(401,'Unable to verify account') from None

def renewal_record(uid):
    key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
    query=urllib.parse.urlencode({'user_id':'eq.'+uid,'select':'subscription_id,plan,currency,paid_until'})
    req=urllib.request.Request('https://unauvicwfjnfqyrtexhy.supabase.co/rest/v1/catpdf_subscriptions?'+query,headers={'apikey':key,'Authorization':'Bearer '+key})
    with urllib.request.urlopen(req,timeout=10) as r: rows=json.load(r)
    if len(rows)>1: raise ValueError('Ambiguous subscription')
    return rows[0] if rows else None

def renewal_validate(sub,record,uid):
    meta=sub.get('metadata') or {}
    if (sub.get('id')!=record['subscription_id'] or sub.get('livemode') is not False or meta.get('user_id')!=uid or meta.get('choice')!=record['plan']+'_'+record['currency']+'_auto'):
        raise HTTPException(409,'Subscription ownership or plan mismatch')
    if not isinstance(sub.get('cancel_at_period_end'),bool): raise ValueError('Missing renewal status')
    return {'plan':record['plan'],'paid_until':record['paid_until'],'status':sub.get('status'),'cancel_at_period_end':sub['cancel_at_period_end'],'cancel_at':sub.get('cancel_at'),'manageable':sub.get('status') in ('active','trialing')}

def renewal_log(stage, error):
    # Never log exception messages, URLs, response bodies or credentials.
    status=error.code if isinstance(error,urllib.error.HTTPError) else None
    print("CatPDF renewal diagnostic:",json.dumps({"stage":stage,"error_type":type(error).__name__,"http_status":status}),flush=True)

def renewal_operation(uid,desired=None):
    if not os.getenv('STRIPE_SECRET_KEY','').startswith('sk_test_'): raise HTTPException(503,'Sandbox unavailable')
    stage="supabase_read"
    try:
        record=renewal_record(uid)
        if not record:
            if desired is not None: raise HTTPException(409,'No recurring subscription')
            return {'subscription':None}
        sid=record['subscription_id']
        if not sid.startswith('sub_'): raise ValueError('Invalid subscription')
        path='subscriptions/'+urllib.parse.quote(sid,safe='')
        stage='stripe_read'
        sub=stripe_get(path)
        stage='stripe_validate'
        state=renewal_validate(sub,record,uid)
        if desired is not None:
            if not state['manageable']: raise HTTPException(409,'Subscription cannot be changed; contact support')
            # Do not clear a separately scheduled cancellation silently.
            if not desired and state['cancel_at'] and not state['cancel_at_period_end']: raise HTTPException(409,'Custom cancellation requires support')
            if state['cancel_at_period_end']!=desired:
                key=os.environ['STRIPE_SECRET_KEY']
                req=urllib.request.Request('https://api.stripe.com/v1/'+path,data=urllib.parse.urlencode({'cancel_at_period_end':str(desired).lower()}).encode(),headers={'Authorization':'Basic '+base64.b64encode((key+':').encode()).decode(),'Content-Type':'application/x-www-form-urlencoded','Idempotency-Key':str(uuid.uuid4())},method='POST')
                stage="stripe_update"
                try:
                    with urllib.request.urlopen(req,timeout=15) as r: json.load(r)
                except Exception as e:
                    renewal_log(stage,e) # Verify authoritative state even after timeout.
                stage="stripe_verify"
                state=renewal_validate(stripe_get(path),record,uid)
                if state['cancel_at_period_end']!=desired: raise HTTPException(503,'Change not confirmed; refresh and retry')
        return {'subscription':state}
    except HTTPException: raise
    except Exception as e:
        renewal_log(stage,e)
        raise HTTPException(503,'Renewal service unavailable; refresh and retry') from None

@router.get('/payments/renewal')
def get_renewal(request: Request):
    return renewal_operation(renewal_account(request))

@router.post('/payments/renewal')
def set_renewal(body: RenewalChoice,request: Request):
    return renewal_operation(renewal_account(request),body.cancel_at_period_end)
