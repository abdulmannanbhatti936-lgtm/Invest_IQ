import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { X } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import type { ReactNode } from 'react';
import type { FilerStatus, GeneratePortfolioRequest, RiskCategory } from '@investiq/shared-types';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { capitalError, cleanCapital, commissionError } from './portfolioView';

// Messages are i18n keys, translated at render time so they follow the language toggle
const schema = z.object({
  capital: z.string().superRefine((value, ctx) => {
    const error = capitalError(value);
    if (error) ctx.addIssue({ code: z.ZodIssueCode.custom, message: error });
  }),
  filer_status: z.enum(['filer', 'non_filer']),
  shariah_only: z.boolean(),
  commission_pct: z.string().superRefine((value, ctx) => {
    const error = commissionError(value);
    if (error) ctx.addIssue({ code: z.ZodIssueCode.custom, message: error });
  }),
});

type FormValues = z.infer<typeof schema>;

export interface PortfolioFormInitial {
  capital: string;
  filerStatus: FilerStatus;
  shariahOnly: boolean;
  commissionPct: string;
}

export const PortfolioForm = ({
  category,
  initial,
  excluded,
  onIncludeAgain,
  onSubmit,
  submitting,
  serverError,
  title,
}: {
  category: RiskCategory;
  initial?: PortfolioFormInitial;
  excluded: string[];
  onIncludeAgain: (ticker: string) => void;
  onSubmit: (body: GeneratePortfolioRequest) => void;
  submitting: boolean;
  serverError?: ReactNode;
  /** Omitted when a surrounding heading already names the form */
  title?: string;
}) => {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: 'onTouched',
    defaultValues: {
      capital: initial?.capital ?? '',
      filer_status: initial?.filerStatus ?? 'filer',
      shariah_only: initial?.shariahOnly ?? false,
      commission_pct: initial?.commissionPct ?? '',
    },
  });

  const submit = (values: FormValues) =>
    onSubmit({
      capital: cleanCapital(values.capital),
      filer_status: values.filer_status,
      shariah_only: values.shariah_only,
      excluded_tickers: excluded,
      ...(values.commission_pct.trim() ? { commission_pct: values.commission_pct.trim() } : {}),
    });

  return (
    <form className="space-y-6" onSubmit={handleSubmit(submit)} noValidate>
      <div>
        {title && <h2 className="text-lg font-semibold text-ink">{title}</h2>}
        <p className="mt-2 text-sm text-muted">
          {t('portfolio.form.intro', { category: t(`risk.${category}`) })}
        </p>
      </div>

      <Input
        label={t('portfolio.form.capital')}
        inputMode="decimal"
        autoComplete="off"
        dir="ltr"
        required
        error={errors.capital?.message ? t(errors.capital.message) : undefined}
        {...register('capital')}
      />

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-ink">{t('portfolio.form.filerStatus')}</legend>
        {(['filer', 'non_filer'] as const).map((status) => (
          <label key={status} className="flex items-center gap-2 text-sm text-ink">
            <input type="radio" value={status} {...register('filer_status')} />
            {t(status === 'filer' ? 'portfolio.form.filer' : 'portfolio.form.nonFiler')}
          </label>
        ))}
        <p className="text-xs text-muted">{t('portfolio.form.filerHelp')}</p>
      </fieldset>

      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" {...register('shariah_only')} />
          {t('portfolio.form.shariah')}
        </label>
        <p className="text-xs text-muted">{t('portfolio.form.shariahHelp')}</p>
      </div>

      <div className="space-y-2">
        <Input
          label={t('portfolio.form.commission')}
          inputMode="decimal"
          autoComplete="off"
          dir="ltr"
          error={errors.commission_pct?.message ? t(errors.commission_pct.message) : undefined}
          {...register('commission_pct')}
        />
        <p className="text-xs text-muted">{t('portfolio.form.commissionHelp')}</p>
      </div>

      {excluded.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {excluded.map((ticker) => (
            <button
              key={ticker}
              type="button"
              onClick={() => onIncludeAgain(ticker)}
              className="inline-flex items-center gap-2 rounded-full border border-line-strong px-4 py-2 text-xs text-ink hover:bg-sunken"
              aria-label={t('portfolio.form.include', { ticker })}
            >
              <bdi dir="ltr">{ticker}</bdi>
              <X className="h-3 w-3" />
            </button>
          ))}
        </div>
      )}

      {serverError}

      <Button type="submit" isLoading={submitting}>
        {t('portfolio.form.submit')}
      </Button>
    </form>
  );
};
