(() => {
'use strict';
const url='https://unauvicwfjnfqyrtexhy.supabase.co', key='sb_publishable_y9pVKZ47UfWibxYaoOcoAg_3mlqpDPs';
const redirect='https://razief12.github.io/CatPDF-Beta/';
const button=document.getElementById('cpAccount'), dialog=document.getElementById('cpAuth'), form=document.getElementById('cpAuthForm'), msg=document.getElementById('cpAuthMessage');
const email=document.getElementById('cpEmail'), password=document.getElementById('cpPassword'), submit=document.getElementById('cpSubmit'), title=document.getElementById('cpAuthTitle'), profile=document.getElementById('cpProfile');
let client, user=null, mode='login', busy=false, recovery=false;
const say=(s)=>{msg.textContent=s;};
function view(m){mode=m; say(''); title.textContent=({login:'Log in',register:'Create account',forgot:'Reset password',reset:'Choose new password',profile:'My Dashboard'})[m];form.hidden=m==='profile';profile.hidden=m!=='profile';email.hidden=m==='reset';email.required=m!=='reset'&&m!=='profile';password.hidden=m==='forgot';password.required=m!=='forgot'&&m!=='profile';password.autocomplete=m==='login'?'current-password':'new-password';document.getElementById('cpShow').hidden=m==='forgot'||m==='profile';submit.textContent=({login:'Log in',register:'Register',forgot:'Send reset link',reset:'Save password'})[m]||'';document.getElementById('cpAuthNav').hidden=m==='profile'||m==='reset';password.value='';password.type='password';document.getElementById('cpShow').textContent='Show password';renderProfile();}
function open(m){view(m);if(!dialog.open)dialog.showModal();}
function update(session){user=session?.user||null;button.textContent=user?'Dashboard':'Log in';renderProfile();}
button.addEventListener('click',()=>open(recovery?'reset':user?'profile':'login'));
document.getElementById('cpClose').onclick=()=>dialog.close();
document.querySelectorAll('[data-cp-mode]').forEach(b=>b.onclick=()=>view(b.dataset.cpMode));
document.getElementById('cpShow').onclick=e=>{password.type=password.type==='password'?'text':'password';e.target.textContent=password.type==='password'?'Show password':'Hide password';};
const el=id=>document.getElementById(id);
function renderProfile(){el('cpProfileEmail').textContent=user?.email||'';el('cpName').textContent=user?.user_metadata?.display_name||'Not set';el('cpNameInput').value=user?.user_metadata?.display_name||'';}
const info=el('cpInfo');
function showInfo(title,html){el('cpInfoTitle').textContent=title;el('cpInfoBody').innerHTML=html;if(!info.open)info.showModal();}
el('cpInfoClose').onclick=()=>info.close();
el('cpQuota').onclick=()=>showInfo('Download allowance',`<p>Usage tracking is not enabled in this beta.</p><p>Planned allowance: ${user?'Free: 2 downloads/day':'Guest: 1 download/day'}.</p><p>Actual remaining downloads will appear once quota tracking is enabled.</p>`);
el('cpBell').onclick=()=>showInfo('Notifications','<p>No account notifications available yet.</p><p>Download alerts and subscription reminders will be enabled with usage tracking and billing.</p>');
el('cpPlans').onclick=()=>{showInfo('Upcoming plans','<p>Preview only. Purchases are not available yet. Translation remains disabled.</p><label for="cpCurrency">Currency</label> <select id="cpCurrency"><option>MYR</option><option>USD</option></select><div id="cpPriceCards" class="cp-grid"></div>');const plans=[['Free','0','0','2/day'],['Daily Pass','7.90','1.99','5 total · 24 hours'],['Monthly Pro','35.90','8.99','10/day · 1 month'],['Quarterly Pro','96.90','24.29','15/day · 3 months']];function prices(){const usd=el('cpCurrency').value==='USD';el('cpPriceCards').innerHTML=plans.map(([n,m,u,q])=>`<section><h3>${n}</h3><p>${usd?'$'+u:'RM'+m}</p><p>${q}</p></section>`).join('');}el('cpCurrency').onchange=prices;prices();};
el('cpNameForm').onsubmit=async e=>{e.preventDefault();if(!user||busy)return;busy=true;try{const {data,error}=await client.auth.updateUser({data:{display_name:el('cpNameInput').value.trim()}});if(error)throw error;user=data.user;renderProfile();say('Profile saved.');}catch(e){say(e.message||'Profile update failed.');}finally{busy=false;}};
el('cpPasswordLink').onclick=async()=>{if(!user||busy)return;busy=true;try{const {error}=await client.auth.resetPasswordForEmail(user.email,{redirectTo:redirect});if(error)throw error;say('Check your email for a password reset link.');}catch(e){say(e.message||'Unable to send reset link.');}finally{busy=false;}};
if(!window.supabase){button.disabled=true;button.title='Authentication unavailable';return;}
client=window.supabase.createClient(url,key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}});
client.auth.onAuthStateChange((event,session)=>{update(session);if(event==='PASSWORD_RECOVERY'){recovery=true;open('reset');}if(event==='SIGNED_OUT')recovery=false;});
client.auth.getSession().then(({data})=>update(data.session)).catch(()=>{});
form.addEventListener('submit',async e=>{e.preventDefault();if(busy)return;busy=true;submit.disabled=true;say('Please wait…');const m=mode;try{let r;const em=email.value.trim(),pw=password.value;if(m==='register'||m==='reset'){if(pw.length<8||!/[a-z]/.test(pw)||!/[A-Z]/.test(pw)||!/\d/.test(pw))throw Error('Use at least 8 characters, including uppercase, lowercase and a number.');}if(m==='login')r=await client.auth.signInWithPassword({email:em,password:pw});else if(m==='register')r=await client.auth.signUp({email:em,password:pw,options:{emailRedirectTo:redirect}});else if(m==='forgot')r=await client.auth.resetPasswordForEmail(em,{redirectTo:redirect});else if(m==='reset')r=await client.auth.updateUser({password:pw});else return;if(r.error)throw r.error;if(m==='register'&&!r.data.session){view('login');say('Check your email for a confirmation link.');}else if(m==='forgot'){say('If the account exists, check your email for a reset link.');}else {if(r.data?.user)user=r.data.user;if(m==='reset')recovery=false;view('profile');say(m==='reset'?'Password updated.':'Signed in.');}}catch(err){say(err.message||'Authentication failed. Try again.');}finally{busy=false;submit.disabled=false;}});
document.getElementById('cpLogout').onclick=async()=>{try{const {error}=await client.auth.signOut();if(error)throw error;view('login');say('Signed out.');}catch(e){say(e.message);}};
})();
