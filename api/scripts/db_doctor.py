"""Diagnose a database connection failure, layer by layer.

    uv run python -m scripts.db_doctor              # ADMIN_DATABASE_URL (what Alembic uses)
    uv run python -m scripts.db_doctor --app        # DATABASE_URL (what the API uses)
    uv run python -m scripts.db_doctor --test       # TEST_DATABASE_URL (what pytest uses)
    uv run python -m scripts.db_doctor --url "postgresql://..."

"Connection error" is four different problems with four different fixes, and the
only thing that tells them apart is WHERE the attempt dies. So this walks the
stack in order  -  DNS, then raw TCP, then the Postgres/TLS handshake, then a real
query  -  and stops at the first failure with the fix for that specific layer.

The distinction that matters most on a managed database:

    TCP times out   -> packets are being DROPPED. A firewall/allowlist. The
                      server never saw you, so it is NOT a connection limit,
                      NOT a password problem, and NOT SSL.
    TCP refused     -> you reached the host but nothing is listening there.
                      Usually the wrong port.
    TCP connects,   -> you reached Postgres and it answered. Now the error text
    then FATAL        is authoritative: credentials, SSL, connection slots, or
                      a missing database.

Read-only: it opens one connection, runs three SELECTs, and closes.
"""

import argparse
import pathlib
import re
import socket
import ssl
import sys
import time
from urllib.parse import urlsplit

# A diagnostic must never itself crash. Windows consoles default to cp1252, which
# cannot encode the arrows/dashes below, and an unhandled UnicodeEncodeError here
# would hide the very error we were called to explain.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ENV_PATH = pathlib.Path(__file__).resolve().parent.parent / ".env"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def redact(url: str) -> str:
    return re.sub(r"://([^:]+):[^@]+@", r"://\1:***@", url)


def say(ok: bool | None, msg: str) -> None:
    mark = "  ok  " if ok else ("FAIL  " if ok is False else "  ..  ")
    print(f"[{mark}] {msg}")


def fix(*lines: str) -> None:
    print("\n" + "-" * 72)
    print("WHAT TO DO")
    print("-" * 72)
    for ln in lines:
        print(ln)
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", action="store_true", help="check DATABASE_URL")
    ap.add_argument("--test", action="store_true", help="check TEST_DATABASE_URL")
    ap.add_argument("--url", help="check an explicit URL")
    args = ap.parse_args()

    env = load_env()
    if args.url:
        url, label = args.url, "--url"
    else:
        key = ("DATABASE_URL" if args.app
               else "TEST_DATABASE_URL" if args.test
               else "ADMIN_DATABASE_URL")
        url, label = env.get(key, ""), key
    if not url:
        print(f"{label} is not set in {ENV_PATH}")
        return 2

    url = url.replace("postgresql+psycopg2://", "postgresql://")
    u = urlsplit(url)
    host, port, dbname = u.hostname, u.port or 5432, (u.path or "/").lstrip("/")
    print(f"\nChecking {label}")
    print(f"  {redact(url)}")
    print(f"  host={host}  port={port}  db={dbname}  user={u.username}\n")

    # -- 1. DNS ---------------------------------------------------------------
    try:
        ips = sorted({r[4][0] for r in socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)})
        say(True, f"DNS resolves to {', '.join(ips)}")
    except Exception as e:
        say(False, f"DNS lookup failed: {e}")
        fix("The hostname doesn't resolve. Check it for typos, and confirm the",
            "database cluster still exists in your provider's console.")
        return 1

    # -- 2. raw TCP  -  the layer that separates a firewall from everything -----
    t0 = time.time()
    s = socket.socket()
    s.settimeout(15)
    try:
        s.connect((host, port))
        s.close()
        say(True, f"TCP connect to {host}:{port} in {time.time() - t0:.1f}s")
    except TimeoutError:
        say(False, f"TCP connect TIMED OUT after {time.time() - t0:.1f}s")
        fix(
            "Packets are being dropped before they reach Postgres. The server never",
            "saw you, so this is NOT a connection limit, NOT a wrong password and",
            "NOT an SSL problem. Almost always the database firewall.",
            "",
            "EASIEST FIX - don't fight the firewall at all. The API container",
            "runs `alembic upgrade head` on every start (docker-entrypoint.sh),",
            "and the droplet is ALREADY a trusted source. To migrate prod, just",
            "redeploy the API service in Dokploy and watch the logs for",
            "'[entrypoint] alembic upgrade head'.",
            "",
            "To connect from THIS machine instead:",
            "",
            "DigitalOcean: Databases -> cluster -> Settings -> Trusted Sources.",
            "  Get your IPv4 with:  curl -4 -s ifconfig.me",
            "  ^ the -4 matters. Plain `curl ifconfig.me` on an Indian ISP (Jio,",
            "    Airtel) usually returns an IPv6 address like 2409:40d4:..., and",
            "    DO Trusted Sources accepts IPv4 CIDR only - it rejects that with",
            "    'invalid IP address'. The database endpoint is IPv4-only anyway.",
            "  On CGNAT the IPv4 is shared and rotates, so this needs redoing.",
            "",
            "  Or tunnel through the droplet, which is already trusted and needs",
            "  no allowlist entry at all:",
            "    ssh -N -L 25060:<db-host>:25060 root@<droplet-ip>",
            "  then point the URL at localhost:25060 (keep sslmode=require;",
            "  it encrypts without verifying the hostname, so the tunnel is fine).",
            "",
            "Aiven: Service -> Overview -> Allowed IP addresses (accepts IPv6).",
            "",
            "Also check: the cluster isn't paused/resizing, and your network isn't",
            "blocking outbound high ports (try a phone hotspot to rule it out).",
        )
        return 1
    except ConnectionRefusedError:
        say(False, f"TCP connection REFUSED on port {port}")
        fix(
            f"You reached {host} but nothing is listening on {port}.",
            "On DigitalOcean the direct port is usually 25060 and the connection",
            "POOL is a different port (often 25061) with its own database name.",
            "Copy the connection string fresh from the console.",
        )
        return 1
    except Exception as e:
        say(False, f"TCP connect failed: {type(e).__name__}: {e}")
        return 1

    # -- 3. TLS ---------------------------------------------------------------
    if "sslmode=disable" not in url:
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection((host, port), timeout=15) as raw:
                # Postgres needs an SSLRequest packet before the TLS handshake.
                raw.sendall((8).to_bytes(4, "big") + (80877103).to_bytes(4, "big"))
                if raw.recv(1) == b"S":
                    with ctx.wrap_socket(raw, server_hostname=host) as tls:
                        say(True, f"TLS handshake OK ({tls.version()})")
                else:
                    say(False, "Server refused SSL  -  it may not be configured for TLS")
        except Exception as e:
            say(False, f"TLS probe failed: {type(e).__name__}: {e}")

    # -- 4. Postgres auth + a real query --------------------------------------
    try:
        import psycopg2
    except ImportError:
        say(False, "psycopg2 not installed  -  run `uv sync --extra dev` first")
        return 1

    try:
        conn = psycopg2.connect(url, connect_timeout=20)
    except psycopg2.OperationalError as e:
        text = str(e).strip()
        say(False, f"Postgres refused the connection:\n         {text.splitlines()[0]}")
        low = text.lower()
        if "too many clients" in low or "remaining connection slots" in low:
            fix(
                "THIS is a real connection-limit problem  -  the server answered and",
                "said it has no slots left.",
                "",
                "Free them, then re-check:",
                "  SELECT pid, usename, application_name, state,",
                "         now() - state_change AS idle_for",
                "  FROM pg_stat_activity WHERE datname = current_database()",
                "  ORDER BY state_change;",
                "",
                "  -- kill sessions idle for over 10 minutes (never your own):",
                "  SELECT pg_terminate_backend(pid) FROM pg_stat_activity",
                "  WHERE datname = current_database() AND pid <> pg_backend_pid()",
                "    AND state = 'idle' AND now() - state_change > interval '10 minutes';",
                "",
                "Then cap the app's pool so it stops happening. In DOKPLOY env vars",
                "(api/.env is in .dockerignore and never reaches the container):",
                "  DB_POOL_SIZE=3   DB_MAX_OVERFLOW=2   WEB_CONCURRENCY=1",
                "Each worker holds up to pool_size+max_overflow; the entrypoint runs",
                "2 workers by default, so the shipped default is 10 per container.",
            )
        elif "password authentication failed" in low:
            fix("The password is wrong or was rotated. Copy the connection string",
                "again from the provider console and update api/.env.")
        elif "no pg_hba.conf entry" in low and "ssl off" in low:
            fix("The server requires TLS. Append `?sslmode=require` to the URL.")
        elif "does not exist" in low:
            fix(f"The database {dbname!r} doesn't exist on that cluster.",
                "Check the name  -  DO's default is often `defaultdb`.")
        elif "starting up" in low or "shutting down" in low:
            fix("The cluster is restarting. Wait a minute and try again.")
        else:
            fix("Full error above. TCP and TLS both succeeded, so the problem is",
                "inside Postgres  -  credentials, database name, or server state.")
        return 1

    say(True, "Postgres authenticated")
    cur = conn.cursor()

    cur.execute("SELECT current_user, current_database(), version()")
    user, db, version = cur.fetchone()
    say(True, f"connected as {user} to {db}")
    print(f"         {version.split(',')[0]}")

    cur.execute("SHOW max_connections")
    max_conn = int(cur.fetchone()[0])
    cur.execute("SELECT count(*) FROM pg_stat_activity")
    used = int(cur.fetchone()[0])
    say(True, f"connections in use: {used} / {max_conn}")
    cur.execute(
        """
        SELECT coalesce(usename,'?'), coalesce(application_name,'(none)'),
               coalesce(state,'?'), count(*)
        FROM pg_stat_activity
        GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 12
        """
    )
    rows = cur.fetchall()
    if rows:
        print("\n         who is holding them:")
        print(f"         {'user':<22}{'application':<26}{'state':<14}count")
        for un, app, st, n in rows:
            print(f"         {un[:21]:<22}{app[:25]:<26}{st[:13]:<14}{n}")

    try:
        cur.execute("SELECT version_num FROM alembic_version")
        heads = [r[0] for r in cur.fetchall()]
        say(True, f"alembic_version = {heads}")
        if heads == ["d8e9f0a1b2c3"]:
            print("         -> already at head  -  SF-1 + HW-1 are applied.")
        elif heads == ["d5e6f7a8b9c0"]:
            print("         -> SF-1 + HW-1 not applied yet. Run: uv run alembic upgrade head")
        elif len(heads) > 1:
            print("         -> MULTIPLE HEADS  -  resolve before upgrading.")
    except Exception:
        conn.rollback()
        say(False, "no alembic_version table  -  this database has never been migrated")

    conn.close()
    print("\nAll layers OK.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
