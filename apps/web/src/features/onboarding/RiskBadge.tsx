import { Rocket, Scale, Shield } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import type { RiskCategory } from '@investiq/shared-types';

// One colour + icon per category, used everywhere the profile appears (Design.md §5, §17).
// Never the gain or loss colours, so a profile is not read as a result.
const STYLE: Record<RiskCategory, { icon: typeof Shield; className: string }> = {
  conservative: { icon: Shield, className: 'bg-primary-tint text-primary border-primary' },
  moderate: { icon: Scale, className: 'bg-sunken text-ink border-line-strong' },
  aggressive: { icon: Rocket, className: 'bg-warning-tint text-warning border-warning' },
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
        size === 'lg' ? 'px-4 py-2 text-base' : 'min-h-8 px-2 text-sm'
      }`}
    >
      <Icon className={size === 'lg' ? 'h-5 w-5' : 'h-4 w-4'} aria-hidden="true" />
      {t(`risk.${category}`)}
    </span>
  );
};
