import { Gauge, Scale, Shield } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import type { RiskCategory } from '@investiq/shared-types';

// One colour + icon per category, used everywhere the profile appears (Design.md §17)
const STYLE: Record<RiskCategory, { icon: typeof Shield; className: string }> = {
  conservative: { icon: Shield, className: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  moderate: { icon: Scale, className: 'bg-sky-50 text-sky-800 border-sky-200' },
  aggressive: { icon: Gauge, className: 'bg-orange-50 text-orange-800 border-orange-200' },
};

export const RiskBadge = ({
  category,
  size = 'md',
}: {
  category: RiskCategory;
  size?: 'md' | 'lg';
}) => {
  const { t } = useTranslation();
  const { icon: Icon, className } = STYLE[category];
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border font-semibold ${className} ${
        size === 'lg' ? 'px-4 py-2 text-base' : 'px-3 py-1 text-sm'
      }`}
    >
      <Icon className={size === 'lg' ? 'h-5 w-5' : 'h-4 w-4'} />
      {t(`risk.${category}`)}
    </span>
  );
};
