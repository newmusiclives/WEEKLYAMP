"""Internationalization foundation.

Provides translation infrastructure for future multi-language editions.
Currently supports: English (default), Spanish, Portuguese, French.
"""

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish (Español)",
    "pt": "Portuguese (Português)",
    "fr": "French (Français)",
}

# Newsletter UI strings — extend as needed
TRANSLATIONS = {
    "en": {
        "subscribe": "Subscribe Free",
        "unsubscribe": "Unsubscribe",
        "read_more": "Read More",
        "share": "Share This Issue",
        "powered_by": "Powered by TrueFans NEWSLETTERS",
        "weekly_digest": "Your Weekly Music Digest",
    },
    "es": {
        "subscribe": "Suscríbete Gratis",
        "unsubscribe": "Cancelar Suscripción",
        "read_more": "Leer Más",
        "share": "Compartir Este Número",
        "powered_by": "Impulsado por TrueFans NEWSLETTERS",
        "weekly_digest": "Tu Resumen Musical Semanal",
    },
    "pt": {
        "subscribe": "Inscreva-se Grátis",
        "unsubscribe": "Cancelar Inscrição",
        "read_more": "Leia Mais",
        "share": "Compartilhe Esta Edição",
        "powered_by": "Desenvolvido por TrueFans NEWSLETTERS",
        "weekly_digest": "Seu Resumo Musical Semanal",
    },
    "fr": {
        "subscribe": "S'abonner Gratuitement",
        "unsubscribe": "Se Désabonner",
        "read_more": "Lire la Suite",
        "share": "Partager Ce Numéro",
        "powered_by": "Propulsé par TrueFans NEWSLETTERS",
        "weekly_digest": "Votre Résumé Musical Hebdomadaire",
    },
}


def t(key: str, lang: str = "en") -> str:
    """Get translated string. Falls back to English if not found."""
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, key))


def get_supported_languages() -> dict:
    return SUPPORTED_LANGUAGES
