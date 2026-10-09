import i18n, { isRTL, SUPPORTED_LANGUAGES, type SupportedLanguage } from '@investiq/i18n';

const KEY = 'investiq.language';

const applyToDocument = (language: string) => {
  document.documentElement.lang = language;
  document.documentElement.dir = isRTL(language) ? 'rtl' : 'ltr';
};

export const setLanguage = (language: SupportedLanguage) => {
  void i18n.changeLanguage(language);
  try {
    localStorage.setItem(KEY, language);
  } catch {
    // ignore: preference just won't persist
  }
};

/** Restore the saved language and keep <html dir/lang> in sync with i18n. */
export const initLanguage = () => {
  let saved: string | null = null;
  try {
    saved = localStorage.getItem(KEY);
  } catch {
    saved = null;
  }
  if (saved && (SUPPORTED_LANGUAGES as readonly string[]).includes(saved)) {
    void i18n.changeLanguage(saved);
  }
  applyToDocument(i18n.language);
  i18n.on('languageChanged', applyToDocument);
};
