-- Run in Supabase SQL Editor as project owner. No client write access.
create table if not exists public.catpdf_entitlements (
 user_id uuid primary key references auth.users(id) on delete cascade,
 plan text not null check(plan in ('daily','monthly','quarterly')),
 expires_at timestamptz not null,
 period_id uuid not null default gen_random_uuid()
);
create table if not exists public.catpdf_usage (
 user_id uuid not null references auth.users(id) on delete cascade,
 bucket text not null, used integer not null default 0 check(used>=0), primary key(user_id,bucket)
);
alter table public.catpdf_entitlements enable row level security;
alter table public.catpdf_usage enable row level security;
revoke all on public.catpdf_entitlements, public.catpdf_usage from anon, authenticated;
create table if not exists public.catpdf_devices (
 device_id uuid primary key, user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(), last_seen timestamptz not null default now()
);
create table if not exists public.catpdf_active_sessions (
 user_id uuid primary key references auth.users(id) on delete cascade, session_id text not null
);
alter table public.catpdf_devices enable row level security;
alter table public.catpdf_active_sessions enable row level security;
revoke all on public.catpdf_devices, public.catpdf_active_sessions from anon, authenticated;
drop function if exists public.catpdf_quota(boolean,text);
create or replace function public.catpdf_quota(p_consume boolean default false,p_tool text default '',p_device uuid default null,p_activate boolean default false) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare uid uuid := auth.uid(); pl text := 'free'; expiry timestamptz; pid uuid; cap integer := 2; n integer := 0; b text; allowed boolean := true; reason text := ''; reset_at timestamptz; owner_id uuid; sid text := auth.jwt()->>'session_id'; device_cap integer; active_sid text;
begin
 if uid is null then raise exception 'Login required'; end if;
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(uid::text,0));
 select e.plan,e.expires_at,e.period_id into pl,expiry,pid from public.catpdf_entitlements e where e.user_id=uid and e.expires_at>now();
 pl:=coalesce(pl,'free');
 if p_device is null or sid is null then raise exception 'Device verification required'; end if;
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_device::text,1));
 select d.user_id into owner_id from public.catpdf_devices d where d.device_id=p_device;
 if owner_id is not null and owner_id<>uid then raise exception 'Device already associated with another account'; end if;
 device_cap:=case pl when 'monthly' then 2 when 'quarterly' then 3 else 1 end;
 if owner_id is null then
   if not p_activate then raise exception 'Sign in to activate this device'; end if;
   if (select count(*) from public.catpdf_devices d where d.user_id=uid)>=device_cap then raise exception 'Device limit reached; contact support'; end if;
   insert into public.catpdf_devices(device_id,user_id) values(p_device,uid);
 end if;
 if p_activate then insert into public.catpdf_active_sessions(user_id,session_id) values(uid,sid) on conflict(user_id) do update set session_id=excluded.session_id; end if;
 select a.session_id into active_sid from public.catpdf_active_sessions a where a.user_id=uid;
 if active_sid is distinct from sid then raise exception 'Session inactive; sign in again'; end if;
 update public.catpdf_devices set last_seen=now() where device_id=p_device;
 cap:=case pl when 'daily' then 5 when 'monthly' then 10 when 'quarterly' then 15 else 2 end;
 b:=case when pl='daily' then 'pass:'||pid::text else 'day:'||((now() at time zone 'UTC')::date)::text end;
 reset_at:=case when pl='daily' then expiry else ((date_trunc('day',now() at time zone 'UTC')+interval '1 day') at time zone 'UTC') end;
 select u.used into n from public.catpdf_usage u where u.user_id=uid and u.bucket=b; n:=coalesce(n,0);
 if p_tool in ('pdfdocx','pdfxlsx','pdfpptx','ocrpdf','ocrimg') and pl='free' then allowed:=false; reason:='Premium tool. Upgrade your plan.';
 elsif n>=cap then allowed:=false; reason:='Download limit reached.';
 elsif p_consume then insert into public.catpdf_usage(user_id,bucket,used) values(uid,b,1) on conflict(user_id,bucket) do update set used=public.catpdf_usage.used+1 returning used into n;
 end if;
 return jsonb_build_object('plan',pl,'limit',cap,'remaining',greatest(0,cap-n),'allowed',allowed,'reason',reason,'reset_at',reset_at,'expires_at',expiry);
end; $$;
revoke all on function public.catpdf_quota(boolean,text,uuid,boolean) from public,anon;
grant execute on function public.catpdf_quota(boolean,text,uuid,boolean) to authenticated;
