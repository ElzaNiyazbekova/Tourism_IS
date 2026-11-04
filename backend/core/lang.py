"""Pick the language for translated content: ?lang=ru|kk|en, else the user's preference, else English."""
from django.conf import settings


def request_lang(request) -> str:
    lang = (request.query_params.get("lang") or "").lower()
    if lang in settings.SUPPORTED_LANGUAGES:
        return lang
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.preferred_language in settings.SUPPORTED_LANGUAGES:
        return user.preferred_language
    return "en"


def pick_translation(translations, lang):
    """translations: an iterable of PackageTranslation (already prefetched). Fallback: en, then any."""
    by_lang = {t.language_code: t for t in translations}
    return by_lang.get(lang) or by_lang.get("en") or next(iter(by_lang.values()), None)
