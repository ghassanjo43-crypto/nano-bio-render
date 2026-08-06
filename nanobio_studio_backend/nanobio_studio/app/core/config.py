"""
Core configuration for NanoBio Studio backend.
Loads environment variables and provides application settings.
"""
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+psycopg://nanobio:nanobio@localhost:5432/nanobio_studio"

    # API
    api_title: str = "NanoBio Studio Backend API"
    api_version: str = "0.1.0"
    debug: bool = True
    log_level: str = "INFO"

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"

    # Application
    app_name: str = "nanobio_studio"
    environment: str = "development"
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8501", "*"]

    # --- Vertical slice (Phase 2) ------------------------------------------
    # Explicit CORS allow-list. Kept separate from `cors_origins` above, which
    # contains a "*" wildcard that is unsafe and is also ignored by browsers
    # when credentials are enabled.
    #
    # This is INERT in the intended deployment. The React dev server proxies
    # /api, /health and /ready to this backend (frontend/vite.config.ts), and
    # production serves the built SPA from this same app (`serve_frontend`
    # below), so in both cases the browser makes same-origin requests and CORS
    # never comes into play. The list exists only for a deployment that
    # deliberately splits the SPA and the API across origins -- which would also
    # require the session cookie to become `SameSite=None; Secure` over HTTPS.
    #
    # Override per-environment, e.g.
    #   $env:SLICE_CORS_ORIGINS = '["https://app.example.com"]'
    slice_cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- Same-origin frontend serving ---------------------------------------
    # When enabled, the built SPA is served from this application so that the
    # interface and the API share one origin.
    #
    # This is a correctness setting, not a packaging convenience. The session
    # cookie is `SameSite=Lax`: if the SPA is served from a different site than
    # the API, the browser accepts the cookie on the login response and then
    # refuses to send it on every subsequent request, signing the user out the
    # instant they sign in. Serving both from one origin removes the cross-site
    # request entirely and keeps the stronger `Lax` CSRF posture.
    #
    # Off by default so API-only development and the test suite are untouched.
    #   $env:SERVE_FRONTEND = "true"
    serve_frontend: bool = False

    #: Location of the Vite build output. Relative paths resolve against the
    #: repository root. Must be built first (`npm run build`).
    frontend_dist_path: str = "frontend/dist"

    # --- Invitation delivery -------------------------------------------------
    # Provider-neutral. The default sends nothing and returns the one-time link
    # to the administrator who created the invitation, which is the honest
    # behaviour for an installation with no mail service: an invitation that
    # silently failed to send is indistinguishable from one that arrived.
    #
    # "recorded" (default) | "console" (development, logs the link) | "smtp".
    #   $env:INVITATION_DELIVERY = "smtp"
    invitation_delivery: str = "recorded"

    #: Where the acceptance link points. Relative by default, so it resolves
    #: against whatever origin serves the application. An absolute value must
    #: be http(s) with a host; anything else is refused at link-build time
    #: rather than turned into an open redirect.
    invitation_link_base: str = "/invitations/accept"

    #: How long an invitation stays redeemable. Short by default: the link is a
    #: credential for an account that does not exist yet, so nobody would
    #: notice it being used.
    invitation_ttl_hours: int = 72

    # SMTP, when `invitation_delivery = "smtp"`. Every value is empty by
    # default and read from the environment — there is deliberately no
    # credential, host or sender in this file, and SmtpDelivery refuses to
    # construct rather than guessing one.
    #   $env:SMTP_HOST / SMTP_PORT / SMTP_USERNAME / SMTP_PASSWORD /
    #   SMTP_FROM_ADDRESS / SMTP_USE_TLS
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    smtp_use_tls: bool = True

    # --- Object storage ------------------------------------------------------
    # Provider-neutral. One driver speaks to AWS S3, Cloudflare R2, MinIO and
    # every other S3-compatible service; what differs between them is the
    # endpoint, the region and whether path-style addressing is needed — three
    # settings, not three code paths.
    #
    #   "local" (default) | "s3"
    #
    # The default is local so that a fresh checkout runs without any cloud
    # account. It is development storage: unencrypted bytes in a directory,
    # stated plainly rather than implied to be more.
    #   $env:STORAGE_DRIVER = "s3"
    storage_driver: str = "local"

    #: Where the local driver writes. Relative paths resolve against the
    #: working directory. Ignored by the s3 driver.
    storage_local_root: str = "var/attachments"

    # S3-compatible settings. Every one is empty by default and read from the
    # environment — there is deliberately no endpoint, bucket or credential in
    # this file, and S3ObjectStore refuses to construct rather than guessing.
    #
    #   $env:STORAGE_BUCKET        = "nanobio-attachments"
    #   $env:STORAGE_ENDPOINT_URL  = "https://<account>.r2.cloudflarestorage.com"
    #   $env:STORAGE_REGION        = "auto"
    #   $env:STORAGE_ACCESS_KEY_ID = "<key id>"
    #   $env:STORAGE_SECRET_ACCESS_KEY = "<secret>"
    #   $env:STORAGE_PATH_STYLE    = "true"     # MinIO and most self-hosted
    storage_bucket: str = ""
    #: Absent for AWS; present for R2, MinIO and other compatible services.
    storage_endpoint_url: str = ""
    storage_region: str = ""
    storage_access_key_id: str = ""
    storage_secret_access_key: str = ""
    #: Needed where virtual-host addressing would require wildcard DNS.
    storage_path_style: bool = False
    #: Optional key prefix, for a bucket shared with something else.
    storage_prefix: str = ""

    #: Server-side encryption. "AES256" is provider-managed and works on AWS
    #: and most compatible gateways; R2 and MinIO encrypt at rest regardless.
    #: Set `storage_sse_kms_key_id` for a customer-managed key — the setting is
    #: a key *identifier*, so it is not tied to one cloud's product.
    storage_sse: str = "AES256"
    storage_sse_kms_key_id: str = ""

    #: How long a presigned URL stays valid, if one is ever issued.
    #:
    #: Nothing issues one today: medical-report documents and registry
    #: attachments are streamed through the authenticated API, because a
    #: presigned URL is a bearer credential that outlives the authorization
    #: that produced it. Kept short so that enabling presigned delivery later
    #: is a decision about a documented performance requirement rather than an
    #: accident of a default.
    storage_presigned_ttl_seconds: int = 300

    #: Upload ceiling, in bytes. Enforced before anything is written.
    storage_max_upload_bytes: int = 25 * 1024 * 1024

    # --- Accounts and sessions ----------------------------------------------
    #: Where activation and password-reset links point. Relative by default, so
    #: it resolves against whatever origin serves the application. An absolute
    #: value must be http(s) with a host; anything else is refused at link-build
    #: time rather than turned into an open redirect.
    account_link_base: str = ""

    #: Session cookie flags. `secure` must be true anywhere reachable over
    #: HTTPS; it is false by default only so local http development works.
    #:   $env:SESSION_COOKIE_SECURE = "true"
    session_cookie_secure: bool = False
    #: "lax" allows normal top-level navigation to carry the cookie while
    #: blocking cross-site form posts. "strict" is stricter and breaks links
    #: from email, which this application sends.
    session_cookie_samesite: str = "lax"
    #: Narrow the cookie to the application path. "/" is correct while the SPA
    #: and the API share an origin, which is the supported deployment.
    session_cookie_path: str = "/"
    #: Left empty so the cookie is host-only. Setting a parent domain would
    #: share it with every sibling host, which is how one compromised
    #: subdomain becomes an authenticated session everywhere.
    session_cookie_domain: str = ""

    #: Proxies whose forwarded client address may be believed.
    #:
    #: Empty means trust none, which is the safe default: an unfiltered
    #: X-Forwarded-For is client-controlled, so honouring it lets an attacker
    #: pick a new "IP" per request and walk straight past per-address rate
    #: limiting. Set to the addresses of your own load balancers only.
    #:   $env:TRUSTED_PROXY_IPS = '["10.0.0.4"]'
    #: Optional path to a sorted pwned-passwords SHA-1 corpus. When unset,
    #: passwords are checked against the embedded common-password list only —
    #: accepted for a small administrator-provisioned population, and to be
    #: set before this platform is opened to self-registration.
    password_breach_corpus_path: str | None = None

    # --- login rate limiting -------------------------------------------
    #: Where failed-login counters live. "memory" is per-process and correct
    #: only for a single instance; "redis" shares them across every process.
    rate_limit_backend: str = "memory"

    #: Required when rate_limit_backend is "redis".
    rate_limit_redis_url: str | None = None

    #: How many application instances will run. Declaring more than one with
    #: the memory backend is refused at startup, because the configured limit
    #: would silently be multiplied by the instance count.
    app_instance_count: int = 1

    trusted_proxy_ips: List[str] = []

    #: Whether a malware scanner is actually connected.
    #:
    #: Left false, and the API reports "not scanned" rather than "clean". A
    #: platform that claims scanning it does not perform is worse than one that
    #: admits it: the claim is what stops somebody adding a scanner.
    storage_malware_scanning_enabled: bool = False
    #: Name of the connected provider, when one is. Never a credential.
    storage_malware_scanner: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
