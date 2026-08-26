import i18next from 'i18next';
import en from './locales/en.json';
import ur from './locales/ur.json';

i18next.init({
  lng: 'en',
  fallbackLng: 'en',
  resources: {
    en: { translation: en },
    ur: { translation: ur },
  },
});

export default i18next;
