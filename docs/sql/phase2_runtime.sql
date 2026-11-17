-- REVIEW ONLY: operator-run grants AFTER 0001_cloud. Does not create a role,
-- set a password, change Supabase built-in roles, or grant BYPASSRLS.
-- Provision resumeiq_runtime separately as described in FASTAPI_PHASE2.md.
BEGIN;
DO $guard$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'resumeiq_runtime') THEN
        RAISE EXCEPTION 'Provision a dedicated resumeiq_runtime role first';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'resumeiq_runtime'
               AND (rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls)) THEN
        RAISE EXCEPTION 'Runtime must have no administrative attributes or BYPASSRLS';
    END IF;
    -- Reject inherited/settable admin privileges and Data API impersonation.
    IF EXISTS (
        SELECT 1 FROM pg_auth_members m
        WHERE m.member = (SELECT oid FROM pg_roles WHERE rolname = 'resumeiq_runtime')
    ) OR EXISTS (
        SELECT 1 FROM pg_roles r
        WHERE r.rolname IN ('anon', 'authenticated', 'service_role', 'authenticator')
        AND pg_has_role(r.oid, 'resumeiq_runtime', 'MEMBER')
    ) THEN
        RAISE EXCEPTION 'Unsafe runtime role membership; review before granting';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
               WHERE n.nspname = 'public' AND c.relname IN
                 ('cloud_resumes', 'cloud_analyses', 'cloud_saved_resumes', 'cloud_history', 'alembic_version')
               AND c.relowner = (SELECT oid FROM pg_roles WHERE rolname = 'resumeiq_runtime')) THEN
        RAISE EXCEPTION 'Runtime must not own cloud or migration tables';
    END IF;
    IF has_schema_privilege('resumeiq_runtime', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'Runtime inherits public schema CREATE; review schema ACLs';
    END IF;
END $guard$;
GRANT USAGE ON SCHEMA public TO resumeiq_runtime;
REVOKE ALL PRIVILEGES ON TABLE public.alembic_version FROM resumeiq_runtime;
REVOKE ALL PRIVILEGES ON TABLE public.cloud_resumes, public.cloud_analyses,
    public.cloud_saved_resumes, public.cloud_history FROM resumeiq_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.cloud_resumes,
    public.cloud_analyses, public.cloud_saved_resumes, public.cloud_history TO resumeiq_runtime;
-- Never GRANT ALL, CREATE, TRUNCATE, REFERENCES, TRIGGER, or WITH GRANT OPTION.
COMMIT;
