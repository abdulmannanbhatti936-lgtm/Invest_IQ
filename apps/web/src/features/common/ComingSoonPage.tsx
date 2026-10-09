import { Construction } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';

/** Placeholder for routes whose feature belongs to a later roadmap phase (Phases.md). */
export const ComingSoonPage = ({ section, phase }: { section: string; phase: number }) => {
  const { t } = useTranslation();
  return (
    <div className="mx-auto mt-12 flex max-w-lg flex-col items-center rounded-xl border border-dashed border-gray-200 bg-white p-12 text-center">
      <Construction className="mb-4 h-10 w-10 text-gray-400" />
      <h1 className="mb-2 text-xl font-semibold text-gray-900">
        {t('common.comingSoonTitle', { section: t(`nav.${section}`) })}
      </h1>
      <p className="text-sm text-gray-500">{t('common.comingSoonBody', { phase })}</p>
    </div>
  );
};
