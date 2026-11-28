begin;
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
 if p_plan in ('monthly','quarterly') then
   delete from public.catpdf_usage where user_id=p_user and bucket='day:'||((now() at time zone 'UTC')::date)::text;
 end if;
 delete from public.catpdf_checkout_locks where user_id=p_user and reservation=p_reservation;
 return jsonb_build_object('activated',true,'expires_at',expiry);
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
   delete from public.catpdf_usage where user_id=p_user and bucket='day:'||((now() at time zone 'UTC')::date)::text;
   insert into public.catpdf_subscriptions values(p_user,p_subscription,p_plan,p_currency,expiry);
 end if;
 insert into public.catpdf_invoices(invoice_id,user_id,subscription_id,plan,amount_minor,currency) values(p_invoice,p_user,p_subscription,p_plan,p_amount,p_currency);
 update public.catpdf_subscriptions set paid_until=greatest(paid_until,expiry) where user_id=p_user;
 insert into public.catpdf_entitlements(user_id,plan,expires_at,period_id) values(p_user,p_plan,expiry,gen_random_uuid()) on conflict(user_id) do update set expires_at=greatest(public.catpdf_entitlements.expires_at,excluded.expires_at),plan=excluded.plan,period_id=case when public.catpdf_entitlements.plan<>excluded.plan then excluded.period_id else public.catpdf_entitlements.period_id end;
 delete from public.catpdf_checkout_locks where user_id=p_user and reservation=p_reservation;
 return jsonb_build_object('activated',true,'expires_at',expiry);
end; $$;
revoke all on function public.catpdf_fulfill_invoice_v1(text,text,uuid,uuid,text,integer,text,bigint,bigint) from public,anon,authenticated;
grant execute on function public.catpdf_fulfill_invoice_v1(text,text,uuid,uuid,text,integer,text,bigint,bigint) to service_role;
commit;
