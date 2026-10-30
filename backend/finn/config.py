from pathlib import Path
import os

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]


def load_local_env() -> None:
    """Local secrets stay untracked; deployed environment variables take precedence."""
    load_dotenv(ROOT / ".env.local", override=False)


def first_env(*names: str) -> str:
    return next((os.environ[name].strip() for name in names if os.environ.get(name, "").strip()), "")


def supabase_configuration() -> tuple[str, str, str]:
    # Accept the user's public URL/key aliases, but NEVER a public-prefixed secret.
    return (
        first_env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
        first_env("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY"),
        first_env("SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"),
    )


def configuration_status() -> dict[str, bool]:
    """Return booleans only. Never return secret values or partial key fingerprints."""
    url, secret, public = supabase_configuration()
    return {
        "gemini": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "supabase": bool(url and secret),
        "public_cache": bool(url and public),
        "semantic_search_enabled": os.getenv("FINN_ENABLE_SEMANTIC_SEARCH", "false").lower() == "true",
    }
