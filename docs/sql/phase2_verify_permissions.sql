-- Read-only postflight. Run manually as migration/admin; outputs no credentials.
SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolcanlogin
FROM pg_roles WHERE rolname = 'resumeiq_runtime';
SELECT n.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity,
       pg_get_userbyid(c.relowner) AS owner
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname IN
 ('cloud_resumes','cloud_analyses','cloud_saved_resumes','cloud_history','alembic_version');
-- Expect zero rows: explicit PUBLIC grants on these tables.
SELECT c.relname, a.privilege_type
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN LATERAL aclexplode(c.relacl) a
WHERE n.nspname = 'public' AND a.grantee = 0 AND c.relname IN
 ('cloud_resumes','cloud_analyses','cloud_saved_resumes','cloud_history','alembic_version');
-- Expect false for every existing Data API role/table pair, including service_role.
SELECT r.rolname, t.name,
       has_table_privilege(r.oid, t.name,
           'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') AS has_any_access
FROM pg_roles r CROSS JOIN (VALUES ('public.cloud_resumes'), ('public.cloud_analyses'),
 ('public.cloud_saved_resumes'), ('public.cloud_history'), ('public.alembic_version')) t(name)
WHERE r.rolname IN ('anon','authenticated','service_role');
SELECT t.name,
       has_table_privilege('resumeiq_runtime', t.name, 'SELECT') AS can_select,
       has_table_privilege('resumeiq_runtime', t.name, 'INSERT') AS can_insert,
       has_table_privilege('resumeiq_runtime', t.name, 'UPDATE') AS can_update,
       has_table_privilege('resumeiq_runtime', t.name, 'DELETE') AS can_delete,
       has_table_privilege('resumeiq_runtime', t.name, 'TRUNCATE,REFERENCES,TRIGGER') AS excessive_access
FROM (VALUES ('public.cloud_resumes'), ('public.cloud_analyses'),
 ('public.cloud_saved_resumes'), ('public.cloud_history'), ('public.alembic_version')) t(name);
-- Empty membership output expected for runtime's parent roles and Data API members.
SELECT pg_get_userbyid(m.roleid) AS parent_role, pg_get_userbyid(m.member) AS member
FROM pg_auth_members m
WHERE m.member = (SELECT oid FROM pg_roles WHERE rolname='resumeiq_runtime')
   OR (m.roleid = (SELECT oid FROM pg_roles WHERE rolname='resumeiq_runtime')
       AND m.member IN (SELECT oid FROM pg_roles
                       WHERE rolname IN ('anon','authenticated','service_role','authenticator')));
