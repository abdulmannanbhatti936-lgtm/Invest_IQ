import { Construction } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';

/** Placeholder for routes whose feature belongs to a later roadmap phase (Phases.md). */
export const ComingSoonPage = ({ section, phase }: { section: string; phase: number }) => {
  const { t } = useTranslation();
  return (
    <div className="mx-auto mt-12 flex max-w-lg flex-col items-center rounded-card border border-dashed border-line bg-surface p-12 text-center">
      <Construction className="mb-4 h-10 w-10 text-muted" />
      <h1 className="mb-2 text-xl font-semibold text-ink">
        {t('common.comingSoonTitle', { section: t(`nav.${section}`) })}
      </h1>
      <p className="text-sm text-muted">{t('common.comingSoonBody', { phase })}</p>
    </div>
  );
};
