import locale

from PyQt5.QtCore import QCoreApplication, QTranslator


def translate(context, key):
    return u'%s' % (QCoreApplication.translate(context, key))


def tr(key):
    return u'%s' % (QCoreApplication.translate("@default", key))


def get_translator_for(locale_id):
    translator = QTranslator()
    translator.load(locale_id, "tribler-gui/tribler_gui/i18n")
    return translator


def get_default_system_translator():
    defaultLocale = locale.getdefaultlocale()[0]
    return get_translator_for(defaultLocale)
