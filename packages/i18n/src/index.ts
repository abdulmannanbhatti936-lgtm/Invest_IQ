import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en.json';
import ur from './locales/ur.json';

export const SUPPORTED_LANGUAGES = ['en', 'ur'] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

/** Urdu is written right-to-left (Design.md §23). */
export const isRTL = (language: string): boolean => language.startsWith('ur');

export const resources = {
  en: { translation: en },
  ur: { translation: ur },
} as const;

if (!i18n.isInitialized) {
  void i18n.use(initReactI18next).init({
    lng: 'en',
    fallbackLng: 'en',
    supportedLngs: [...SUPPORTED_LANGUAGES],
    resources,
    interpolation: { escapeValue: false }, // React already escapes
  });
}

export { useTranslation, Trans } from 'react-i18next';
export default i18n;
