"""Provision the restricted app role on a fresh Postgres cluster.

Architectural law 2 is only real if the app connects as a role that CANNOT bypass
RLS. Managed-Postgres admin roles (Aiven's `avnadmin`, DigitalOcean's `doadmin`)
all have `rolbypassrls = true`, so pointing DATABASE_URL at one silently disables
every org_isolation policy in the schema. That role belongs in ADMIN_DATABASE_URL
only, where alembic uses it.

The migrations create the policies but never GRANT anything, so this script also
installs DEFAULT PRIVILEGES — run it BEFORE `alembic upgrade head` and every table
the migrations create is automatically usable by the app role. It is idempotent
and safe to re-run afterwards (it re-grants over existing objects too).

Usage (PowerShell):
    cd api
    $env:DO_ADMIN_BASE = 'postgresql://doadmin:PASSWORD@host:25060/'   # trailing slash
    uv run python -m scripts.provision_app_role

The admin URL is read from the environment so no credential is stored in the repo.
Prints the generated password once — copy it into DATABASE_URL in api/.env.
"""

import os
import secrets
import sys

import psycopg2

APP_DB = os.environ.get("APP_DB", "trackbit_school")
APP_ROLE = os.environ.get("APP_ROLE", "trackbit_school_app")


def main() -> int:
    try:
        admin_base = os.environ["DO_ADMIN_BASE"]
    except KeyError:
        print("DO_ADMIN_BASE is not set (needs a trailing slash).", file=sys.stderr)
        return 2

    if not admin_base.endswith("/"):
        admin_base += "/"

    password = secrets.token_urlsafe(24)

    # 1) Roles are cluster-level objects — create from the maintenance database.
    conn = psycopg2.connect(f"{admin_base}defaultdb?sslmode=require")
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT rolcreaterole FROM pg_roles WHERE rolname = current_user")
    row = cur.fetchone()
    if not row or not row[0]:
        print("admin role lacks CREATEROLE — create the user in the DO control panel "
              "instead, then re-run with APP_ROLE set to it.", file=sys.stderr)
        return 1

    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
    if cur.fetchone():
        cur.execute(f'ALTER ROLE "{APP_ROLE}" WITH LOGIN NOBYPASSRLS PASSWORD %s', (password,))
        print(f"role {APP_ROLE}: existed -> password rotated")
    else:
        cur.execute(f'CREATE ROLE "{APP_ROLE}" WITH LOGIN NOBYPASSRLS PASSWORD %s', (password,))
        print(f"role {APP_ROLE}: created")

    cur.execute(f'GRANT CONNECT ON DATABASE "{APP_DB}" TO "{APP_ROLE}"')
    conn.close()

    # 2) Schema usage + default privileges, inside the target database.
    conn = psycopg2.connect(f"{admin_base}{APP_DB}?sslmode=require")
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(f'GRANT USAGE ON SCHEMA public TO "{APP_ROLE}"')
    cur.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{APP_ROLE}"')
    cur.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                f'GRANT USAGE, SELECT ON SEQUENCES TO "{APP_ROLE}"')
    cur.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public '
                f'TO "{APP_ROLE}"')
    cur.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{APP_ROLE}"')

    cur.execute("SELECT rolbypassrls FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
    bypasses_rls = cur.fetchone()[0]
    print(f"{APP_ROLE} rolbypassrls: {bypasses_rls}   (must be False)")
    conn.close()

    if bypasses_rls:
        print("ABORT: the app role can bypass RLS.", file=sys.stderr)
        return 1

    print("\nCopy this into DATABASE_URL in api/.env — it is not stored anywhere:")
    print(f"  {password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
