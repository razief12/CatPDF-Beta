begin;
create table if not exists public.catpdf_subscriptions(user_id uuid primary key references auth.users(id), subscription_id text unique not null, plan text not null, currency text not null, paid_until timestamptz not null);
create table if not exists public.catpdf_invoices(invoice_id text primary key, user_id uuid not null references auth.users(id), subscription_id text not null, plan text not null, amount_minor integer not null, currency text not null, created_at timestamptz not null default now());
alter table public.catpdf_subscriptions enable row level security;
alter table public.catpdf_invoices enable row level security;
revoke all on public.catpdf_subscriptions,public.catpdf_invoices from public,anon,authenticated;
create or replace function public.catpdf_checkout_reserve(p_user uuid,p_reservation uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare e public.catpdf_entitlements%rowtype; n integer;
begin
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_user::text,0));
 if exists(select 1 from public.catpdf_checkout_locks where user_id=p_user) then return jsonb_build_object('allowed',false,'reason','Existing checkout pending. Complete it or wait for expiry; contact support if blocked.'); end if;
 if exists(select 1 from public.catpdf_subscriptions where user_id=p_user) then return jsonb_build_object('allowed',false,'reason','Existing subscription requires reconciliation or cancellation.'); end if;
 select * into e from public.catpdf_entitlements where user_id=p_user;
 if e.expires_at>now() then
 select used into n from public.catpdf_usage where user_id=p_user and bucket='pass:'||e.period_id::text;
 if e.plan<>'daily' or coalesce(n,0)<5 then return jsonb_build_object('allowed',false,'reason','Active plan: wait for expiry or exhaust your Daily Pass.'); end if;
 end if;
 insert into public.catpdf_checkout_locks(user_id,reservation) values(p_user,p_reservation);
 return jsonb_build_object('allowed',true);
end; $$;

create or replace function public.catpdf_fulfill_invoice_v1(p_invoice text,p_subscription text,p_user uuid,p_reservation uuid,p_plan text,p_amount integer,p_currency text,p_start bigint,p_end bigint) returns jsonb language plpgsql security definer set search_path='' as $$
declare sub public.catpdf_subscriptions%rowtype; e public.catpdf_entitlements%rowtype; n integer; expiry timestamptz;
begin
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_user::text,0));
 if exists(select 1 from public.catpdf_invoices where invoice_id=p_invoice) then return jsonb_build_object('duplicate',true); end if;
 if p_plan not in ('monthly','quarterly') or p_currency not in ('myr','usd') or p_amount<=0 or p_end<=p_start then raise exception 'Invalid invoice'; end if;
 expiry:=pg_catalog.to_timestamp(p_end);
 select * into sub from public.catpdf_subscriptions where user_id=p_user;
 if found then
   if sub.subscription_id<>p_subscription or sub.plan<>p_plan or sub.currency<>p_currency then raise exception 'Subscription conflict'; end if;
 else
   if not exists(select 1 from public.catpdf_checkout_locks where user_id=p_user and reservation=p_reservation) then raise exception 'Missing reservation'; end if;
   select * into e from public.catpdf_entitlements where user_id=p_user;
   if e.expires_at>now() then
     select used into n from public.catpdf_usage where user_id=p_user and bucket='pass:'||e.period_id::text;
     if e.plan<>'daily' or coalesce(n,0)<5 then raise exception 'Active plan conflict'; end if;
   end if;
   insert into public.catpdf_subscriptions values(p_user,p_subscription,p_plan,p_currency,expiry);
 end if;
 insert into public.catpdf_invoices(invoice_id,user_id,subscription_id,plan,amount_minor,currency) values(p_invoice,p_user,p_subscription,p_plan,p_amount,p_currency);
 update public.catpdf_subscriptions set paid_until=greatest(paid_until,expiry) where user_id=p_user;
 insert into public.catpdf_entitlements(user_id,plan,expires_at,period_id) values(p_user,p_plan,expiry,gen_random_uuid()) on conflict(user_id) do update set expires_at=greatest(public.catpdf_entitlements.expires_at,excluded.expires_at),plan=excluded.plan;
 delete from public.catpdf_checkout_locks where user_id=p_user and reservation=p_reservation;
 return jsonb_build_object('activated',true,'expires_at',expiry);
end; $$;
revoke all on function public.catpdf_fulfill_invoice_v1(text,text,uuid,uuid,text,integer,text,bigint,bigint) from public,anon,authenticated;
grant execute on function public.catpdf_fulfill_invoice_v1(text,text,uuid,uuid,text,integer,text,bigint,bigint) to service_role;
create or replace function public.catpdf_payment_history_v2() returns table(plan text,created_at timestamptz,amount_minor integer,currency text,status text) language sql stable security definer set search_path='' as $$
 select * from (select p.plan,p.created_at,p.amount_minor,p.currency,'activated'::text from public.catpdf_manual_payments p where p.user_id=auth.uid() union all select i.plan,i.created_at,i.amount_minor,i.currency,'activated'::text from public.catpdf_invoices i where i.user_id=auth.uid()) h order by h.created_at desc limit 50;
$$;
revoke all on function public.catpdf_checkout_reserve(uuid,uuid) from public,anon,authenticated;
grant execute on function public.catpdf_checkout_reserve(uuid,uuid) to service_role;
revoke all on function public.catpdf_payment_history_v2() from public,anon;
grant execute on function public.catpdf_payment_history_v2() to authenticated;
create or replace function public.catpdf_subscription_info() returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object('plan',plan,'paid_until',paid_until,'renewal','automatic') from public.catpdf_subscriptions where user_id=auth.uid();
$$;
revoke all on function public.catpdf_subscription_info() from public,anon;
grant execute on function public.catpdf_subscription_info() to authenticated;
commit;
