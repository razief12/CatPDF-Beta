-- Run after quota.sql. Sandbox only; no client access.
create table if not exists public.catpdf_manual_payments (
 session_id text primary key, intent_id text unique not null,
 user_id uuid not null references auth.users(id) on delete cascade,
 plan text not null check(plan in ('daily','monthly','quarterly')),
 created_at timestamptz not null default now()
);
alter table public.catpdf_manual_payments enable row level security;
revoke all on public.catpdf_manual_payments from public, anon, authenticated;
create or replace function public.catpdf_fulfill_manual(p_session text,p_intent text,p_user uuid,p_plan text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare old_plan text; old_expiry timestamptz; new_expiry timestamptz; duration interval;
begin
 if p_plan not in ('daily','monthly','quarterly') or p_session not like 'cs_test_%' or p_intent not like 'pi_%' then raise exception 'Invalid payment'; end if;
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_user::text,0));
 insert into public.catpdf_manual_payments(session_id,intent_id,user_id,plan) values(p_session,p_intent,p_user,p_plan) on conflict do nothing;
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
revoke all on function public.catpdf_fulfill_manual(text,text,uuid,text) from public,anon,authenticated;
grant execute on function public.catpdf_fulfill_manual(text,text,uuid,text) to service_role;
