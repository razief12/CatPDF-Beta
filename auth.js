(() => {
'use strict';
const url='https://unauvicwfjnfqyrtexhy.supabase.co', key='sb_publishable_y9pVKZ47UfWibxYaoOcoAg_3mlqpDPs';
const redirect='https://razief12.github.io/CatPDF-Beta/';
const button=document.getElementById('cpAccount'), dialog=document.getElementById('cpAuth'), form=document.getElementById('cpAuthForm'), msg=document.getElementById('cpAuthMessage');
const email=document.getElementById('cpEmail'), password=document.getElementById('cpPassword'), submit=document.getElementById('cpSubmit'), title=document.getElementById('cpAuthTitle'), profile=document.getElementById('cpProfile');
let client, user=null, mode='login', busy=false, recovery=false;
const say=(s)=>{msg.textContent=s;};
function view(m){mode=m; say(''); title.textContent=({login:'Log in',register:'Create account',forgot:'Reset password',reset:'Choose new password',profile:'Your account'})[m];form.hidden=m==='profile';profile.hidden=m!=='profile';email.hidden=m==='reset';email.required=m!=='reset'&&m!=='profile';password.hidden=m==='forgot';password.required=m!=='forgot'&&m!=='profile';password.autocomplete=m==='login'?'current-password':'new-password';document.getElementById('cpShow').hidden=m==='forgot'||m==='profile';submit.textContent=({login:'Log in',register:'Register',forgot:'Send reset link',reset:'Save password'})[m]||'';document.getElementById('cpAuthNav').hidden=m==='profile'||m==='reset';password.value='';password.type='password';document.getElementById('cpShow').textContent='Show password';document.getElementById('cpProfileEmail').textContent=user?.email||'';}
function open(m){view(m);if(!dialog.open)dialog.showModal();}
function update(session){user=session?.user||null;button.textContent=user?'Account':'Log in';}
button.addEventListener('click',()=>open(recovery?'reset':user?'profile':'login'));
document.getElementById('cpClose').onclick=()=>dialog.close();
document.querySelectorAll('[data-cp-mode]').forEach(b=>b.onclick=()=>view(b.dataset.cpMode));
document.getElementById('cpShow').onclick=e=>{password.type=password.type==='password'?'text':'password';e.target.textContent=password.type==='password'?'Show password':'Hide password';};
if(!window.supabase){button.disabled=true;button.title='Authentication unavailable';return;}
client=window.supabase.createClient(url,key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}});
client.auth.onAuthStateChange((event,session)=>{update(session);if(event==='PASSWORD_RECOVERY'){recovery=true;open('reset');}if(event==='SIGNED_OUT')recovery=false;});
client.auth.getSession().then(({data})=>update(data.session)).catch(()=>{});
form.addEventListener('submit',async e=>{e.preventDefault();if(busy)return;busy=true;submit.disabled=true;say('Please wait…');const m=mode;try{let r;const em=email.value.trim(),pw=password.value;if(m==='register'||m==='reset'){if(pw.length<8||!/[a-z]/.test(pw)||!/[A-Z]/.test(pw)||!/\d/.test(pw))throw Error('Use at least 8 characters, including uppercase, lowercase and a number.');}if(m==='login')r=await client.auth.signInWithPassword({email:em,password:pw});else if(m==='register')r=await client.auth.signUp({email:em,password:pw,options:{emailRedirectTo:redirect}});else if(m==='forgot')r=await client.auth.resetPasswordForEmail(em,{redirectTo:redirect});else if(m==='reset')r=await client.auth.updateUser({password:pw});else return;if(r.error)throw r.error;if(m==='register'&&!r.data.session){view('login');say('Check your email for a confirmation link.');}else if(m==='forgot'){say('If the account exists, check your email for a reset link.');}else {if(m==='reset')recovery=false;view('profile');say(m==='reset'?'Password updated.':'Signed in.');}}catch(err){say(err.message||'Authentication failed. Try again.');}finally{busy=false;submit.disabled=false;}});
document.getElementById('cpLogout').onclick=async()=>{try{const {error}=await client.auth.signOut();if(error)throw error;view('login');say('Signed out.');}catch(e){say(e.message);}};
})();
