# -*- coding: utf-8 -*-
"""Glass System Utility Warder Evolution localization."""

from __future__ import absolute_import

import gettext
import os

DOMAIN = "GlassSysUtil"
LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locale")

try:
    from Components.Language import language
    language.addCallback(lambda: gettext.bindtextdomain(DOMAIN, LOCALE_DIR))
except Exception:
    language = None

gettext.bindtextdomain(DOMAIN, LOCALE_DIR)


def _(text):
    translated = gettext.dgettext(DOMAIN, text)
    if translated == text:
        translated = gettext.gettext(text)
    return translated
