import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import it from "./locales/it.json";

// Language detection kept deliberately simple for M0: browser language with an
// English fallback. A user-facing switcher + persistence lands in a later
// milestone.
const browserLang = navigator.language?.slice(0, 2);

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    it: { translation: it },
  },
  lng: browserLang === "it" ? "it" : "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
