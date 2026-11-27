-- Additive migration; existing payment records remain intact.
begin;
alter table public.catpdf_manual_payments add column if not exists amount_minor integer check (amount_minor > 0);
alter table public.catpdf_manual_payments add column if not exists currency text check (currency in ('myr','usd'));
create or replace function public.catpdf_fulfill_manual_v2(p_session text,p_intent text,p_user uuid,p_plan text,p_amount integer,p_currency text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare old_plan text; old_expiry timestamptz; new_expiry timestamptz; duration interval;
begin
 if p_amount is null or p_amount <= 0 or p_currency is null or p_currency not in ('myr','usd') then raise exception 'Invalid amount'; end if;
 if p_plan not in ('daily','monthly','quarterly') or p_session not like 'cs_test_%' or p_intent not like 'pi_%' then raise exception 'Invalid payment'; end if;
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_user::text,0));
 insert into public.catpdf_manual_payments(session_id,intent_id,user_id,plan,amount_minor,currency) values(p_session,p_intent,p_user,p_plan,p_amount,p_currency) on conflict do nothing;
 if not found then return jsonb_build_object('duplicate',true); end if;
 select plan,expires_at into old_plan,old_expiry from public.catpdf_entitlements where user_id=p_user;
 duration:=case p_plan when 'daily' then interval '24 hours' when 'monthly' then interval '1 month' else interval '3 months' end;
 -- Never overwrite an active different plan; payment remains in Stripe for manual reconciliation.
 if old_expiry>now() and old_plan<>p_plan then raise exception 'Active different plan requires reconciliation'; end if;
 new_expiry:=greatest(now(),coalesce(old_expiry,now()))+duration;
 insert into public.catpdf_entitlements(user_id,plan,expires_at) values(p_user,p_plan,new_expiry)
 on conflict(user_id) do update set plan=excluded.plan,expires_at=excluded.expires_at,period_id=case when public.catpdf_entitlements.expires_at>now() then public.catpdf_entitlements.period_id else gen_random_uuid() end;
 return jsonb_build_object('activated',true,'expires_at',new_expiry);
end; $$;
revoke all on function public.catpdf_fulfill_manual_v2(text,text,uuid,text,integer,text) from public,anon,authenticated;
grant execute on function public.catpdf_fulfill_manual_v2(text,text,uuid,text,integer,text) to service_role;

create or replace function public.catpdf_payment_history_v2()
returns table(plan text, created_at timestamptz, amount_minor integer, currency text, status text)
language sql stable security definer set search_path='' as $$
 select p.plan,p.created_at,p.amount_minor,p.currency,'activated'::text from public.catpdf_manual_payments p
 where p.user_id=auth.uid() order by p.created_at desc limit 50;
$$;
revoke all on function public.catpdf_payment_history_v2() from public,anon;
grant execute on function public.catpdf_payment_history_v2() to authenticated;
commit;
