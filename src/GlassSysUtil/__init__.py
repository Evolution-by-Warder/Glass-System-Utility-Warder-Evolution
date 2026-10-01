# -*- coding: utf-8 -*-
"""Glass System Utility - Warder Evolution localization."""

from __future__ import absolute_import

import gettext
import os

DOMAIN = "GlassSysUtil"
LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locale")
_translation = gettext.NullTranslations()

try:
    from Components.Language import language
except Exception:
    language = None


def localeInit():
    global _translation
    languages = None
    if language is not None:
        try:
            current = language.getLanguage()
            if current:
                languages = [current, current.split("_", 1)[0].split("-", 1)[0]]
        except Exception:
            languages = None
    try:
        _translation = gettext.translation(DOMAIN, LOCALE_DIR, languages=languages, fallback=True)
    except Exception:
        _translation = gettext.NullTranslations()


localeInit()
if language is not None:
    try:
        language.addCallback(localeInit)
    except Exception:
        pass


def _(text):
    return _translation.gettext(text)
