import { useFieldArray, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Plus, X } from 'lucide-react';
import type { ReactNode } from 'react';
import { useTranslation } from '@investiq/i18n';
import type { BacktestUniverse, RunBacktestRequest } from '@investiq/shared-types';
import { Button } from '../../components/ui/Button';
import { Notice } from '../../components/ui/Feedback';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { formatPctString } from '../../lib/format';
import { capitalError, cleanCapital } from '../portfolio/portfolioView';
import { maxYearsFor, mixProblems, mixTotal, yearOptions } from './backtestView';

// Messages are i18n keys, translated at render time so they follow the language toggle
const schema = z.object({
  capital: z.string().superRefine((value, ctx) => {
    const error = capitalError(value);
    if (error) ctx.addIssue({ code: z.ZodIssueCode.custom, message: error });
  }),
  filer_status: z.enum(['filer', 'non_filer']),
  years: z.string(),
  rows: z.array(z.object({ ticker: z.string(), weight: z.string() })).superRefine((rows, ctx) => {
    const [first] = mixProblems(rows);
    if (first) ctx.addIssue({ code: z.ZodIssueCode.custom, message: first });
  }),
});

type FormValues = z.infer<typeof schema>;

/** FR29 "or custom": the user's own companies and weights, tested like a portfolio. */
export const CustomMixForm = ({
  universe,
  onSubmit,
  submitting,
  serverError,
}: {
  universe: BacktestUniverse;
  onSubmit: (body: RunBacktestRequest) => void;
  submitting: boolean;
  serverError?: ReactNode;
}) => {
  const { t } = useTranslation();
  const {
    control,
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitted },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: 'onTouched',
    defaultValues: {
      capital: '',
      filer_status: 'filer',
      years: String(universe.min_years),
      rows: [
        { ticker: '', weight: '' },
        { ticker: '', weight: '' },
      ],
    },
  });
  const { fields, append, remove } = useFieldArray({ control, name: 'rows' });

  const rows = watch('rows');
  const chosen = rows.map((r) => r.ticker).filter(Boolean);
  const maxYears = chosen.length ? maxYearsFor(universe, chosen) : universe.max_years;
  const years = yearOptions(universe.min_years, maxYears);
  const problems = isSubmitted ? mixProblems(rows) : [];

  const submit = (values: FormValues) =>
    onSubmit({
      years: Math.min(Number(values.years), maxYears ?? universe.min_years),
      custom: {
        capital: cleanCapital(values.capital),
        filer_status: values.filer_status,
        holdings: values.rows.map((r) => ({ ticker: r.ticker, weight_pct: r.weight.trim() })),
      },
    });

  return (
    <form className="space-y-6" onSubmit={handleSubmit(submit)} noValidate>
      <div className="space-y-3">
        {fields.map((field, index) => (
          <div key={field.id} className="flex items-end gap-2">
            <div className="min-w-0 flex-1">
              <Select
                label={t('backtest.mix.company')}
                hideLabel={index > 0}
                {...register(`rows.${index}.ticker`)}
              >
                <option value="">{t('backtest.mix.choose')}</option>
                {universe.stocks.map((s) => (
                  <option key={s.ticker} value={s.ticker}>
                    {s.ticker} · {s.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="w-36 shrink-0">
              <Input
                label={t('backtest.mix.weight')}
                hideLabel={index > 0}
                inputMode="decimal"
                autoComplete="off"
                dir="ltr"
                {...register(`rows.${index}.weight`)}
              />
            </div>
            <button
              type="button"
              onClick={() => remove(index)}
              disabled={fields.length === 1}
              className="mb-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 disabled:opacity-30"
              aria-label={t('backtest.mix.remove')}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
        <div className="flex items-center justify-between">
          <Button
            type="button"
            variant="secondary"
            onClick={() => append({ ticker: '', weight: '' })}
          >
            <Plus className="me-2 h-4 w-4" />
            {t('backtest.mix.addRow')}
          </Button>
          <p className="text-sm font-medium tabular-nums text-gray-700">
            {t('backtest.mix.totalLabel', { total: formatPctString(mixTotal(rows)) })}
          </p>
        </div>
        {problems.length > 0 && (
          <ul role="alert" className="space-y-1 text-xs text-red-600">
            {problems.map((key) => (
              <li key={key}>{t(key)}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <Input
          label={t('portfolio.form.capital')}
          inputMode="decimal"
          autoComplete="off"
          dir="ltr"
          required
          error={errors.capital?.message ? t(errors.capital.message) : undefined}
          {...register('capital')}
        />
        <Select label={t('backtest.landing.period')} {...register('years')}>
          {years.map((y) => (
            <option key={y} value={y}>
              {t('backtest.landing.yearsOption', { years: y })}
            </option>
          ))}
        </Select>
      </div>
      {chosen.length > 0 && maxYears != null && (
        <p className="text-xs text-gray-500">{t('backtest.mix.maxYears', { years: maxYears })}</p>
      )}

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-gray-700">
          {t('portfolio.form.filerStatus')}
        </legend>
        {(['filer', 'non_filer'] as const).map((status) => (
          <label key={status} className="flex items-center gap-2 text-sm text-gray-800">
            <input type="radio" value={status} {...register('filer_status')} />
            {t(status === 'filer' ? 'portfolio.form.filer' : 'portfolio.form.nonFiler')}
          </label>
        ))}
        <p className="text-xs text-gray-500">{t('portfolio.form.filerHelp')}</p>
      </fieldset>

      {universe.left_out.length > 0 && (
        <Notice>
          {t('backtest.mix.leftOut', {
            tickers: universe.left_out.map((s) => s.ticker).join(', '),
          })}
        </Notice>
      )}

      {serverError}

      <Button type="submit" isLoading={submitting}>
        {submitting ? t('backtest.landing.running') : t('backtest.landing.run')}
      </Button>
    </form>
  );
};
