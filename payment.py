"""Sandbox-only price validation. Checkout intentionally unavailable until fulfillment exists."""
import os, json, urllib.request, base64, asyncio
from fastapi import APIRouter, HTTPException
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
    return {'sandbox':True,'checkout_enabled':False,'all_verified':all(v=='ok' for v in results.values()),'prices':results}
# Verification is opt-in from server startup configuration, not a public API.
@router.get('/payments/status')
def status():
    return {'sandbox':True,'checkout_enabled':False,'price_verification':'see Render startup logs'}
async def startup_verify():
    try:
        result=await asyncio.to_thread(verify)
        print('CatPDF Stripe sandbox verification:',json.dumps(result),flush=True)
    except HTTPException as e:
        print('CatPDF Stripe sandbox verification:',e.detail,flush=True)
