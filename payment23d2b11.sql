begin;
create or replace function public.catpdf_checkout_abort(p_user uuid,p_reservation uuid) returns void language sql security definer set search_path='' as $$
 delete from public.catpdf_checkout_locks where user_id=p_user and reservation=p_reservation and session_id is null;
$$;
revoke all on function public.catpdf_checkout_abort(uuid,uuid) from public,anon,authenticated;
grant execute on function public.catpdf_checkout_abort(uuid,uuid) to service_role;
commit;
