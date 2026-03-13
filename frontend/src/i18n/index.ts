import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import ko from "./locales/ko.json";
import ja from "./locales/ja.json";
import zh from "./locales/zh.json";

const savedLanguage = (() => {
  try {
    return localStorage.getItem("language") || "en";
  } catch {
    return "en";
  }
})();

i18n.use(initReactI18next).init({
  lng: savedLanguage,
  fallbackLng: "en",
  resources: {
    en: { translation: en },
    ko: { translation: ko },
    ja: { translation: ja },
    zh: { translation: zh },
  },
  interpolation: {
    escapeValue: false, // React already escapes values
  },
  // Allow <strong> and basic HTML in Trans component
  react: { transKeepBasicHtmlNodesFor: ["br", "strong", "i", "b", "p"] },
});

export default i18n;
