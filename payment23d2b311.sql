begin;
grant select on public.catpdf_subscriptions to service_role;
commit;
select has_table_privilege('service_role','public.catpdf_subscriptions','SELECT') as backend_can_read,
       has_table_privilege('authenticated','public.catpdf_subscriptions','SELECT') as authenticated_can_read,
       has_table_privilege('anon','public.catpdf_subscriptions','SELECT') as anon_can_read;
