begin;
create table if not exists public.catpdf_checkout_locks(user_id uuid primary key references auth.users(id) on delete cascade, reservation uuid not null unique, session_id text unique, created_at timestamptz not null default now());
alter table public.catpdf_checkout_locks enable row level security;
revoke all on public.catpdf_checkout_locks from public,anon,authenticated;
create or replace function public.catpdf_checkout_pending(p_user uuid) returns text language sql security definer set search_path='' as $$ select session_id from public.catpdf_checkout_locks where user_id=p_user $$;
create or replace function public.catpdf_checkout_release(p_user uuid,p_session text) returns void language sql security definer set search_path='' as $$ delete from public.catpdf_checkout_locks where user_id=p_user and session_id=p_session $$;
create or replace function public.catpdf_checkout_reserve(p_user uuid,p_reservation uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare e public.catpdf_entitlements%rowtype; n integer;
begin
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_user::text,0));
 if exists(select 1 from public.catpdf_checkout_locks where user_id=p_user) then return jsonb_build_object('allowed',false,'reason','Existing checkout pending. Complete it or wait for expiry; contact support if blocked.'); end if;
 select * into e from public.catpdf_entitlements where user_id=p_user;
 if e.expires_at>now() then
 select used into n from public.catpdf_usage where user_id=p_user and bucket='pass:'||e.period_id::text;
 if e.plan<>'daily' or coalesce(n,0)<5 then return jsonb_build_object('allowed',false,'reason','Active plan: wait for expiry or exhaust your Daily Pass.'); end if;
 end if;
 insert into public.catpdf_checkout_locks(user_id,reservation) values(p_user,p_reservation);
 return jsonb_build_object('allowed',true);
end; $$;
create or replace function public.catpdf_checkout_bind(p_user uuid,p_reservation uuid,p_session text) returns void language plpgsql security definer set search_path='' as $$ begin
 update public.catpdf_checkout_locks set session_id=p_session where user_id=p_user and reservation=p_reservation and session_id is null;
 if not found then raise exception 'Missing reservation'; end if;
end; $$;
create or replace function public.catpdf_fulfill_manual_v3(p_session text,p_intent text,p_user uuid,p_plan text,p_amount integer,p_currency text,p_reservation uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare e public.catpdf_entitlements%rowtype; n integer; expiry timestamptz;
begin
 if p_plan not in ('daily','monthly','quarterly') or p_amount is null or p_amount<=0 or p_currency not in ('myr','usd') or p_session not like 'cs_test_%' or p_intent not like 'pi_%' then raise exception 'Invalid payment'; end if;
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_user::text,0));
 if exists(select 1 from public.catpdf_manual_payments where session_id=p_session or intent_id=p_intent) then return jsonb_build_object('duplicate',true); end if;
 if not exists(select 1 from public.catpdf_checkout_locks where user_id=p_user and reservation=p_reservation and session_id=p_session) then raise exception 'Unreserved payment requires reconciliation'; end if;
 select * into e from public.catpdf_entitlements where user_id=p_user;
 if e.expires_at>now() then
 select used into n from public.catpdf_usage where user_id=p_user and bucket='pass:'||e.period_id::text;
 if e.plan<>'daily' or coalesce(n,0)<5 then raise exception 'Active plan requires reconciliation'; end if;
 end if;
 expiry:=now()+case p_plan when 'daily' then interval '24 hours' when 'monthly' then interval '1 month' else interval '3 months' end;
 insert into public.catpdf_manual_payments(session_id,intent_id,user_id,plan,amount_minor,currency) values(p_session,p_intent,p_user,p_plan,p_amount,p_currency);
 insert into public.catpdf_entitlements(user_id,plan,expires_at,period_id) values(p_user,p_plan,expiry,gen_random_uuid()) on conflict(user_id) do update set plan=excluded.plan,expires_at=excluded.expires_at,period_id=excluded.period_id;
 delete from public.catpdf_checkout_locks where user_id=p_user and reservation=p_reservation;
 return jsonb_build_object('activated',true,'expires_at',expiry);
end; $$;
revoke all on function public.catpdf_checkout_pending(uuid) from public,anon,authenticated; grant execute on function public.catpdf_checkout_pending(uuid) to service_role;
revoke all on function public.catpdf_checkout_release(uuid,text) from public,anon,authenticated; grant execute on function public.catpdf_checkout_release(uuid,text) to service_role;
revoke all on function public.catpdf_checkout_reserve(uuid,uuid) from public,anon,authenticated; grant execute on function public.catpdf_checkout_reserve(uuid,uuid) to service_role;
revoke all on function public.catpdf_checkout_bind(uuid,uuid,text) from public,anon,authenticated; grant execute on function public.catpdf_checkout_bind(uuid,uuid,text) to service_role;
revoke all on function public.catpdf_fulfill_manual_v3(text,text,uuid,text,integer,text,uuid) from public,anon,authenticated; grant execute on function public.catpdf_fulfill_manual_v3(text,text,uuid,text,integer,text,uuid) to service_role;
commit;
