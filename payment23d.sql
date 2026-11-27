-- Read-only history of fulfilled manual payments; no direct table grants.
create or replace function public.catpdf_payment_history()
returns table(plan text, created_at timestamptz) language sql stable security definer set search_path='' as $$
 select p.plan,p.created_at from public.catpdf_manual_payments p
 where p.user_id=auth.uid() order by p.created_at desc limit 50;
$$;
revoke all on function public.catpdf_payment_history() from public,anon;
grant execute on function public.catpdf_payment_history() to authenticated;
