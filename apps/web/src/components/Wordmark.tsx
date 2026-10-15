import { useTranslation } from '@investiq/i18n';

/** "Invest" in the text colour, "IQ" in the brand gradient; always Latin, left to right. */
export const Wordmark = ({ className = '' }: { className?: string }) => {
  const { t } = useTranslation();
  const name = t('common.appName');
  return (
    <span dir="ltr" className={`font-bold tracking-tight text-ink ${className}`}>
      {name.slice(0, -2)}
      <span className="bg-gradient-to-r from-gradient-1 via-gradient-2 to-gradient-3 bg-clip-text text-transparent">
        {name.slice(-2)}
      </span>
    </span>
  );
};
