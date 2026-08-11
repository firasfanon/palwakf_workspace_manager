from __future__ import annotations

import hashlib
import json

from palwakf_orchestrator.database_contracts import SchemaCatalogSnapshot

APPROVED_APPLICATION_SCHEMAS: tuple[str, ...] = (
    "assistant",
    "awqaf_system",
    "billing_system",
    "cases",
    "cms",
    "complaints",
    "core",
    "facilities_module",
    "gis",
    "gis_ref",
    "gis_waqf",
    "hist",
    "hist_raw",
    "legacy_quarantine",
    "media_center",
    "ministry_profile",
    "mustakshif_staging",
    "nosok",
    "ontology",
    "platform",
    "platform_access",
    "platform_content",
    "platform_documents",
    "platform_experience",
    "platform_navigation",
    "platform_notifications",
    "platform_reporting",
    "platform_services",
    "platform_technical",
    "public",
    "religious_affairs",
    "site_content",
    "tasks",
    "waqf",
    "zakat",
)

NON_APPLICATION_SCHEMAS: frozenset[str] = frozenset(
    {
        "auth",
        "cron",
        "extensions",
        "graphql",
        "graphql_public",
        "information_schema",
        "net",
        "pg_catalog",
        "pg_toast",
        "pgbouncer",
        "pgsodium",
        "pgsodium_masks",
        "realtime",
        "storage",
        "supabase_functions",
        "supabase_migrations",
        "topology",
        "vault",
    }
)


def compute_schema_catalog_hash(snapshot: SchemaCatalogSnapshot) -> str:
    payload = snapshot.model_dump(mode="json", exclude={"captured_at"})
    payload["boundary_drift_schema_names"] = sorted(payload["boundary_drift_schema_names"])
    payload["approved_schema_names"] = sorted(payload["approved_schema_names"])
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_catalog_boundary(snapshot: SchemaCatalogSnapshot) -> None:
    approved = set(APPROVED_APPLICATION_SCHEMAS)
    supplied = set(snapshot.approved_schema_names)
    if supplied != approved:
        missing = sorted(approved - supplied)
        unexpected = sorted(supplied - approved)
        raise ValueError(
            "APPLICATION_SCHEMA_BOUNDARY_MISMATCH:"
            f"missing={','.join(missing)} unexpected={','.join(unexpected)}"
        )
    if snapshot.boundary_drift_schema_names:
        raise ValueError(
            "UNAPPROVED_SCHEMA_BOUNDARY_DRIFT:"
            + ",".join(sorted(snapshot.boundary_drift_schema_names))
        )


def build_catalog_sql() -> str:
    schema_literals = ", ".join(
        "'" + name.replace("'", "''") + "'" for name in APPROVED_APPLICATION_SCHEMAS
    )
    return f"""
WITH approved(schema_name) AS (
    SELECT unnest(ARRAY[{schema_literals}]::text[])
),
approved_ns AS (
    SELECT n.oid, n.nspname
    FROM pg_namespace n
    JOIN approved a ON a.schema_name = n.nspname
),
relations AS (
    SELECT
        c.oid,
        n.nspname AS schema_name,
        c.relname AS object_name,
        c.relkind,
        c.relrowsecurity,
        c.relforcerowsecurity,
        pg_get_userbyid(c.relowner) AS owner_role
    FROM pg_class c
    JOIN approved_ns n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'p', 'v', 'm')
)
SELECT jsonb_build_object(
    'catalog_version', 'PALWAKF_SCHEMA_CATALOG_R2',
    'database_target_id', 'PALWAKF_CANONICAL_SUPABASE',
    'captured_at', now(),
    'approved_schema_names', (
        SELECT jsonb_agg(schema_name ORDER BY schema_name) FROM approved
    ),
    'boundary_drift_schema_names', '[]'::jsonb,
    'relations', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'schema_name', r.schema_name,
                'object_name', r.object_name,
                'kind', CASE r.relkind
                    WHEN 'r' THEN 'TABLE'
                    WHEN 'p' THEN 'PARTITIONED_TABLE'
                    WHEN 'v' THEN 'VIEW'
                    WHEN 'm' THEN 'MATERIALIZED_VIEW'
                END,
                'owner_role', r.owner_role,
                'rls_enabled', r.relrowsecurity,
                'rls_forced', r.relforcerowsecurity,
                'definition', CASE
                    WHEN r.relkind = 'v' THEN pg_get_viewdef(r.oid, true)
                    WHEN r.relkind = 'm' THEN pg_get_viewdef(r.oid, true)
                    ELSE NULL
                END
            )
            ORDER BY r.schema_name, r.object_name
        )
        FROM relations r
    ), '[]'::jsonb),
    'columns', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'schema_name', r.schema_name,
                'object_name', r.object_name,
                'name', a.attname,
                'data_type', format_type(a.atttypid, a.atttypmod),
                'nullable', NOT a.attnotnull,
                'ordinal', a.attnum,
                'default_expression', pg_get_expr(ad.adbin, ad.adrelid),
                'generated', NULLIF(a.attgenerated::text, ''),
                'identity', NULLIF(a.attidentity::text, '')
            )
            ORDER BY r.schema_name, r.object_name, a.attnum
        )
        FROM relations r
        JOIN pg_attribute a ON a.attrelid = r.oid
        LEFT JOIN pg_attrdef ad
          ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
        WHERE a.attnum > 0 AND NOT a.attisdropped
    ), '[]'::jsonb),
    'constraints', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'schema_name', r.schema_name,
                'object_name', r.object_name,
                'constraint_name', con.conname,
                'kind', CASE con.contype
                    WHEN 'p' THEN 'PRIMARY_KEY'
                    WHEN 'f' THEN 'FOREIGN_KEY'
                    WHEN 'u' THEN 'UNIQUE'
                    WHEN 'c' THEN 'CHECK'
                    WHEN 'x' THEN 'EXCLUSION'
                END,
                'columns', COALESCE((
                    SELECT jsonb_agg(a.attname ORDER BY u.ordinality)
                    FROM unnest(con.conkey) WITH ORDINALITY AS u(attnum, ordinality)
                    JOIN pg_attribute a
                      ON a.attrelid = con.conrelid AND a.attnum = u.attnum
                ), '[]'::jsonb),
                'referenced_schema_name', rn.nspname,
                'referenced_object_name', rc.relname,
                'referenced_columns', COALESCE((
                    SELECT jsonb_agg(a.attname ORDER BY u.ordinality)
                    FROM unnest(con.confkey) WITH ORDINALITY AS u(attnum, ordinality)
                    JOIN pg_attribute a
                      ON a.attrelid = con.confrelid AND a.attnum = u.attnum
                ), '[]'::jsonb),
                'definition', pg_get_constraintdef(con.oid, true)
            )
            ORDER BY r.schema_name, r.object_name, con.conname
        )
        FROM pg_constraint con
        JOIN relations r ON r.oid = con.conrelid
        LEFT JOIN pg_class rc ON rc.oid = con.confrelid
        LEFT JOIN pg_namespace rn ON rn.oid = rc.relnamespace
        WHERE con.contype IN ('p', 'f', 'u', 'c', 'x')
    ), '[]'::jsonb),
    'indexes', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'schema_name', r.schema_name,
                'object_name', r.object_name,
                'index_name', idx.relname,
                'unique', i.indisunique,
                'primary', i.indisprimary,
                'valid', i.indisvalid,
                'definition', pg_get_indexdef(i.indexrelid)
            )
            ORDER BY r.schema_name, r.object_name, idx.relname
        )
        FROM pg_index i
        JOIN relations r ON r.oid = i.indrelid
        JOIN pg_class idx ON idx.oid = i.indexrelid
    ), '[]'::jsonb),
    'functions', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'schema_name', n.nspname,
                'function_name', p.proname,
                'identity_arguments', pg_get_function_identity_arguments(p.oid),
                'result_type', pg_get_function_result(p.oid),
                'language', l.lanname,
                'security_definer', p.prosecdef,
                'volatility', p.provolatile::text,
                'parallel_safety', p.proparallel::text
            )
            ORDER BY n.nspname, p.proname, pg_get_function_identity_arguments(p.oid)
        )
        FROM pg_proc p
        JOIN approved_ns n ON n.oid = p.pronamespace
        JOIN pg_language l ON l.oid = p.prolang
    ), '[]'::jsonb),
    'triggers', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'schema_name', r.schema_name,
                'object_name', r.object_name,
                'trigger_name', t.tgname,
                'enabled', t.tgenabled::text,
                'definition', pg_get_triggerdef(t.oid, true)
            )
            ORDER BY r.schema_name, r.object_name, t.tgname
        )
        FROM pg_trigger t
        JOIN relations r ON r.oid = t.tgrelid
        WHERE NOT t.tgisinternal
    ), '[]'::jsonb),
    'policies', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'schema_name', r.schema_name,
                'object_name', r.object_name,
                'policy_name', p.polname,
                'command', p.polcmd::text,
                'permissive', p.polpermissive,
                'roles', COALESCE((
                    SELECT jsonb_agg(pg_get_userbyid(role_oid) ORDER BY pg_get_userbyid(role_oid))
                    FROM unnest(p.polroles) role_oid
                ), '[]'::jsonb),
                'using_expression', pg_get_expr(p.polqual, p.polrelid),
                'check_expression', pg_get_expr(p.polwithcheck, p.polrelid)
            )
            ORDER BY r.schema_name, r.object_name, p.polname
        )
        FROM pg_policy p
        JOIN relations r ON r.oid = p.polrelid
    ), '[]'::jsonb),
    'enums', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'schema_name', n.nspname,
                'enum_name', t.typname,
                'values', (
                    SELECT jsonb_agg(e.enumlabel ORDER BY e.enumsortorder)
                    FROM pg_enum e WHERE e.enumtypid = t.oid
                )
            )
            ORDER BY n.nspname, t.typname
        )
        FROM pg_type t
        JOIN approved_ns n ON n.oid = t.typnamespace
        WHERE t.typtype = 'e'
    ), '[]'::jsonb),
    'grants', COALESCE((
        SELECT jsonb_agg(g ORDER BY g->>'schema_name', g->>'object_name', g->>'grantee')
        FROM (
            SELECT jsonb_build_object(
                'object_kind', 'TABLE_OR_VIEW',
                'schema_name', table_schema,
                'object_name', table_name,
                'grantee', grantee,
                'privileges', jsonb_agg(privilege_type ORDER BY privilege_type)
            ) AS g
            FROM information_schema.role_table_grants
            WHERE table_schema IN (SELECT schema_name FROM approved)
            GROUP BY table_schema, table_name, grantee
            UNION ALL
            SELECT jsonb_build_object(
                'object_kind', 'ROUTINE',
                'schema_name', routine_schema,
                'object_name', routine_name,
                'grantee', grantee,
                'privileges', jsonb_agg(privilege_type ORDER BY privilege_type)
            ) AS g
            FROM information_schema.role_routine_grants
            WHERE routine_schema IN (SELECT schema_name FROM approved)
            GROUP BY routine_schema, routine_name, grantee
        ) grants_union
    ), '[]'::jsonb),
    'dependencies', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'source_schema_name', v.view_schema,
                'source_object_name', v.view_name,
                'target_schema_name', v.table_schema,
                'target_object_name', v.table_name,
                'dependency_type', 'VIEW_USES_RELATION'
            )
            ORDER BY v.view_schema, v.view_name, v.table_schema, v.table_name
        )
        FROM information_schema.view_table_usage v
        WHERE v.view_schema IN (SELECT schema_name FROM approved)
          AND v.table_schema IN (SELECT schema_name FROM approved)
    ), '[]'::jsonb)
) AS catalog;
""".strip()


def build_boundary_drift_sql() -> str:
    approved_literals = ", ".join(
        "'" + name.replace("'", "''") + "'" for name in APPROVED_APPLICATION_SCHEMAS
    )
    non_app_literals = ", ".join(
        "'" + name.replace("'", "''") + "'" for name in sorted(NON_APPLICATION_SCHEMAS)
    )
    return f"""
SELECT n.nspname AS schema_name
FROM pg_namespace n
WHERE n.nspname NOT IN ({approved_literals})
  AND n.nspname NOT IN ({non_app_literals})
  AND n.nspname NOT LIKE 'pg_temp_%'
  AND n.nspname NOT LIKE 'pg_toast_temp_%'
ORDER BY n.nspname;
""".strip()
