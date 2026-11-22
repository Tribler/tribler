import i18n from "i18next";
import {initReactI18next} from "react-i18next";
import HttpBackend from "i18next-http-backend";

i18n.on("languageChanged", (language) => {
    document.documentElement.lang = language.replace("_", "-");
});

i18n.use(HttpBackend)
    .use(initReactI18next)
    .init({
        supportedLngs: ["en_US", "es_ES", "hi_IN", "ko_KR", "pt_BR", "ru_RU", "sv_SE", "zh_CN"],
        lng: "en_US",
        fallbackLng: "en_US",
        interpolation: {
            escapeValue: false,
        },
        backend: {
            loadPath: `${window.location.origin}/locales/{{lng}}.json`,
        },
        load: "currentOnly",
    });

export default i18n;
