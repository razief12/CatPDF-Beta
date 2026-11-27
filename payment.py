"""Sandbox-only price validation. Sandbox checkout preview; fulfillment is not implemented."""
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
    return {'sandbox':True,'checkout_enabled':True,'price_verification':'see Render startup logs'}
async def startup_verify():
    try:
        result=await asyncio.to_thread(verify)
        print('CatPDF Stripe sandbox verification:',json.dumps(result),flush=True)
    except HTTPException as e:
        print('CatPDF Stripe sandbox verification:',e.detail,flush=True)


class CheckoutChoice(BaseModel):
    choice: str

@router.post('/payments/checkout')
def checkout(body: CheckoutChoice, request: Request):
    expected = PRICES.get(body.choice)
    if expected is None: raise HTTPException(400, 'Unknown plan')
    if expected[3]: raise HTTPException(503, 'Automatic renewal is temporarily unavailable')
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
            if old.get('status') == 'expired':
                payment_rpc('catpdf_checkout_release', {'p_user':uid,'p_session':existing})
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
            data.update({'subscription_data[metadata][user_id]':uid,'subscription_data[metadata][choice]':body.choice})
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

def payment_rpc(name, data):
    key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
    req=urllib.request.Request('https://unauvicwfjnfqyrtexhy.supabase.co/rest/v1/rpc/'+name,data=json.dumps(data).encode(),headers={'apikey':key,'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=15) as r: return json.load(r)

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
    if event.get('type') not in ('checkout.session.completed','checkout.session.async_payment_succeeded'): return {'received':True}
    s=event['data']['object']
    if s.get('mode')!='payment' or s.get('payment_status')!='paid': return {'received':True}
    try: await asyncio.to_thread(fulfill_manual,s['id'])
    except Exception as e:
        print('CatPDF fulfillment failed:',type(e).__name__,flush=True)
        raise HTTPException(503,'Fulfillment failed; retry required') from None
    return {'received':True}
