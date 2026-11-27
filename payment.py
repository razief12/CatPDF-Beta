"""Sandbox-only price validation. Sandbox checkout preview; fulfillment is not implemented."""
import os, json, urllib.request, urllib.parse, base64, asyncio, uuid
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
    key = os.environ.get('STRIPE_SECRET_KEY', '')
    if not key.startswith('sk_test_'): raise HTTPException(503, 'Sandbox unavailable')
    token = request.headers.get('authorization', '')
    if not token.startswith('Bearer '): raise HTTPException(401, 'Login required')
    try:
        req = urllib.request.Request('https://unauvicwfjnfqyrtexhy.supabase.co/auth/v1/user', headers={'apikey':'sb_publishable_y9pVKZ47UfWibxYaoOcoAg_3mlqpDPs','Authorization':token})
        with urllib.request.urlopen(req, timeout=10) as r: user=json.load(r)
        uid=str(uuid.UUID(user['id']))
    except Exception: raise HTTPException(401, 'Unable to verify account') from None
    auth = 'Basic '+base64.b64encode((key+':').encode()).decode()
    try:
        req=urllib.request.Request('https://api.stripe.com/v1/prices/'+expected[0],headers={'Authorization':auth})
        with urllib.request.urlopen(req,timeout=10) as r: price=json.load(r)
        if not validate_price(price,expected): raise HTTPException(503,'Price verification failed')
        site='https://razief12.github.io/CatPDF-Beta/'
        data={'mode':'subscription' if expected[3] else 'payment','line_items[0][price]':expected[0],'line_items[0][quantity]':'1','success_url':site+'?payment=test_success','cancel_url':site+'?payment=cancelled','client_reference_id':uid,'metadata[user_id]':uid,'metadata[choice]':body.choice}
        if expected[3]:
            data.update({'subscription_data[metadata][user_id]':uid,'subscription_data[metadata][choice]':body.choice})
        req=urllib.request.Request('https://api.stripe.com/v1/checkout/sessions',data=urllib.parse.urlencode(data).encode(),headers={'Authorization':auth,'Content-Type':'application/x-www-form-urlencoded'},method='POST')
        with urllib.request.urlopen(req,timeout=15) as r: session=json.load(r)
        target=session.get('url','')
        if session.get('livemode') is not False or urllib.parse.urlparse(target).netloc!='checkout.stripe.com' or not target.startswith('https://'): raise HTTPException(503,'Invalid sandbox session')
        return {'url':target,'sandbox':True}
    except HTTPException: raise
    except Exception: raise HTTPException(502,'Unable to create sandbox checkout') from None
