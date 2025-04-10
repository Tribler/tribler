import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import HttpBackend from 'i18next-http-backend';
import { triblerService } from '@/services/tribler.service';

i18n
    .use(HttpBackend)
    .use(initReactI18next)
    .init({
        supportedLngs: ['en_US', 'es_ES', 'hi_IN', 'ko_KR', 'pt_BR', 'ru_RU', 'zh_CN'],
        lng: triblerService.guiSettings.lang,
        fallbackLng: 'en_US',
        interpolation: {
            escapeValue: false,
        },
        backend: {
            loadPath: `${window.location.origin}/locales/{{lng}}.json`,
        },
    });

export default i18n;
