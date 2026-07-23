"""Application configuration settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "TrackBit API"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database. The app connects as a restricted role (no BYPASSRLS) so the RLS
    # safety net actually applies. Migrations run as the privileged owner via
    # ADMIN_DATABASE_URL (falls back to DATABASE_URL if unset).
    DATABASE_URL: str = "postgresql+psycopg2://trackbit:trackbit@localhost:5434/trackbit"
    ADMIN_DATABASE_URL: str = ""
    TEST_DATABASE_URL: str = "postgresql+psycopg2://trackbit:trackbit@localhost:5434/trackbit_test"
    # Per-engine connection budget. Kept small on purpose: the managed Postgres caps
    # `max_connections` at 20, and SQLAlchemy's own defaults (5 + 10 overflow) let a
    # single process eat three quarters of that. Raise only alongside the server's cap.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5

    @property
    def migration_database_url(self) -> str:
        return self.ADMIN_DATABASE_URL or self.DATABASE_URL

    # JWT
    JWT_SECRET_KEY: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Auth token lifetimes (hours)
    MAGIC_LINK_EXPIRE_HOURS: int = 72
    INVITE_LINK_EXPIRE_HOURS: int = 7 * 24
    PASSWORD_RESET_EXPIRE_HOURS: int = 24

    # Credential rules
    PASSWORD_MIN_LENGTH: int = 8
    USERNAME_MIN_LENGTH: int = 3
    USERNAME_MAX_LENGTH: int = 32

    # Security
    BCRYPT_ROUNDS: int = 12
    RATE_LIMIT_ENABLED: bool = True

    # Frontend (magic/invite links point here)
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Background jobs. Enable on exactly ONE instance (never multi-worker).
    ENABLE_SCHEDULER: bool = False

    # Self-serve org registration. Schools are created by the platform operator
    # (super-admin) who runs setup and hands over credentials — set this False in
    # production. Defaults True so dev + the test suite keep working.
    ALLOW_PUBLIC_ORG_SIGNUP: bool = True

    # How often last_active_at is allowed to be written per member (seconds)
    LAST_ACTIVE_THROTTLE_SECONDS: int = 300

    # Email (Resend). Empty key => dev console adapter (logs instead of sending).
    # Per-purpose senders, all on the verified notify.trackbit.in domain.
    # RESEND_FROM is the general/default identity (digests, report cards, and any
    # mail that doesn't pick a more specific sender).
    RESEND_API_KEY: str = ""
    RESEND_FROM: str = "TrackBit <hello@notify.trackbit.in>"
    # Account-access links: invites, password reset (the "login"/magic-link mails).
    RESEND_FROM_LOGIN: str = "TrackBit <login@notify.trackbit.in>"
    # Task reminder / overdue mails.
    RESEND_FROM_REMINDERS: str = "TrackBit <reminders@notify.trackbit.in>"

    # Web Push (VAPID). Self-generated keypair; public key is exposed to the client.
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:notify@trackbit.app"

    # Default minutes before due_at to send a reminder (per-task override later).
    DEFAULT_REMIND_BEFORE_MINUTES: int = 30

    # Billing (Razorpay). Empty keys => stub mode: the upgrade flow is wired but
    # checkout is disabled until real keys are added (plan P4-BE-01).
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_PLAN_ID: str = ""  # the Pro ₹500/month plan id from the Razorpay dashboard
    RAZORPAY_WEBHOOK_SECRET: str = ""
    PRO_GRACE_DAYS: int = 7  # keep Pro this long after a failed payment before downgrading

    @property
    def billing_configured(self) -> bool:
        return bool(self.RAZORPAY_KEY_ID and self.RAZORPAY_KEY_SECRET and self.RAZORPAY_PLAN_ID)

    # Attachments storage. Empty R2 creds => local-disk fallback (dev): files are
    # written under MEDIA_DIR and served from MEDIA_BASE_URL (plan P4-BE-02).
    MEDIA_DIR: str = "media"
    MEDIA_BASE_URL: str = "http://localhost:8000/media"
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = ""
    R2_PUBLIC_BASE_URL: str = ""  # public/CDN base for objects, e.g. https://cdn.example.com

    @property
    def storage_configured(self) -> bool:
        return bool(
            self.R2_ACCOUNT_ID and self.R2_ACCESS_KEY_ID
            and self.R2_SECRET_ACCESS_KEY and self.R2_BUCKET
        )

    # AI services (SPRD §8), routed through OpenRouter — one OpenAI-compatible
    # endpoint, any model, one key. Empty key => every AI call short-circuits and
    # the caller falls back to its deterministic heuristic, so all drafting and
    # parsing flows stay testable offline. Model ids live in env so upgrading is
    # config, not code. Every AI output lands in a human-confirm surface before
    # persisting (editable drafts, verify grids) — AI never writes to a table.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    # OpenRouter attributes usage to these (both optional; they appear on the
    # openrouter.ai leaderboards and in your usage dashboard).
    OPENROUTER_SITE_URL: str = ""
    OPENROUTER_APP_NAME: str = "TrackBit School"
    # Two models, split by job — not by price.
    #   DRAFT  reasoning and generation: syllabus splitting, question phrasing,
    #          plan drafting. Text in, text out.
    #   PARSE  extraction, INCLUDING from images and PDFs: column mapping, timetable
    #          photos, scanned syllabi. This one MUST be multimodal — a text-only
    #          model here silently degrades every OCR path to the heuristic.
    # `deepseek/deepseek-v4-flash` is text-only; `google/gemini-2.5-flash-lite`
    # accepts image + file. Swapping them would break document ingestion.
    AI_MODEL_DRAFT: str = "deepseek/deepseek-v4-flash"
    AI_MODEL_PARSE: str = "google/gemini-2.5-flash-lite"
    # Ingestion runs while an admin waits on a spinner. Fail fast and fall back to
    # the heuristic rather than hanging the setup wizard on a slow model.
    AI_TIMEOUT_SECONDS: float = 20.0
    # OCR on a scanned syllabus or a timetable photo takes far longer than a text
    # completion; 20s would time out on every one of them and silently fall back.
    AI_VISION_TIMEOUT_SECONDS: float = 90.0
    AI_MAX_RETRIES: int = 1

    @property
    def ai_configured(self) -> bool:
        return bool(self.OPENROUTER_API_KEY)

    # Lucy — the agentic chat layer. One more model slot, split by job like the
    # others: AGENT must be a strong tool-calling model (the loop is useless on a
    # model that can't emit parallel tool_calls reliably). Everything else is the
    # loop's safety rails: caps are hard limits, not tuning knobs — a runaway
    # conversation must end, not degrade the Aiven connection budget.
    AI_MODEL_AGENT: str = "anthropic/claude-sonnet-4.5"
    AI_AGENT_TIMEOUT_SECONDS: float = 45.0  # per model call, not per message
    LUCY_MAX_ITERATIONS: int = 8  # model turns per message
    LUCY_WALL_SECONDS: float = 90.0  # hard wall-clock cap per message
    LUCY_HISTORY_MESSAGES: int = 20  # prior messages replayed to the model
    LUCY_TOOL_RESULT_MAX_CHARS: int = 6000  # model-facing tool result truncation
    # Streaming can be flipped off per-deploy if a model's SSE misbehaves; the
    # loop then buffers each completion and emits the same events at once.
    LUCY_STREAM_TOKENS: bool = True
    LUCY_ACTION_EXPIRE_MINUTES: int = 15  # pending write proposals expire unconfirmed

    # V2-P1 §5.3 — the assisted timetable draft (proposer + validators + repair) is
    # NOT a guaranteed solver, so it ships behind a flag until piloted. Off => the
    # /timetable/draft endpoint reports the feature is disabled.
    TIMETABLE_ASSISTED_DRAFT: bool = False

    # Guardian messaging (SPRD §7). New channel alongside push/email. Empty key =>
    # console stub logs the exact message. Guardians have no app/email, so go-live
    # of guardian notify is gated on these keys; dev + pilot-start run on the stub.
    WHATSAPP_API_KEY: str = ""
    WHATSAPP_SENDER: str = ""

    @property
    def whatsapp_configured(self) -> bool:
        return bool(self.WHATSAPP_API_KEY and self.WHATSAPP_SENDER)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
