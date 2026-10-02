"""One place that decides how we authenticate to Gemini: Vertex AI with Application Default Credentials, or an AI Studio API key."""
from __future__ import annotations

from google import genai
from google.genai import types

from gatorway.config import Settings


def gemini_configured(settings: Settings) -> bool:
    if settings.google_genai_use_vertexai:
        return bool(settings.google_cloud_project)
    return bool(settings.gemini_api_key)


def make_genai_client(settings: Settings) -> genai.Client:
    http = types.HttpOptions(timeout=30_000)  # ms per request
    if settings.google_genai_use_vertexai:
        if not settings.google_cloud_project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is required when GOOGLE_GENAI_USE_VERTEXAI is true")
        return genai.Client(vertexai=True, project=settings.google_cloud_project, location=settings.google_cloud_location, http_options=http)
    if settings.gemini_api_key:
        return genai.Client(api_key=settings.gemini_api_key, http_options=http)
    raise RuntimeError("No Gemini credentials: set GOOGLE_GENAI_USE_VERTEXAI=true (uses gcloud ADC) or GEMINI_API_KEY")
