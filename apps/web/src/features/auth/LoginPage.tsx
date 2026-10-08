import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Link } from 'react-router-dom';
import { getErrorStatus } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import { useAuth } from './AuthContext';
import { AuthShell } from './AuthShell';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';

// Messages are i18n keys, translated at render time so they follow the language toggle
const loginSchema = z.object({
  email: z.string().email({ message: 'auth.validation.emailInvalid' }),
  password: z.string().min(1, { message: 'auth.validation.passwordRequired' }),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export const LoginPage = () => {
  const { t } = useTranslation();
  const { login, sessionExpired } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    mode: 'onTouched', // inline errors on blur, then live while correcting (Design.md §12.3)
  });

  const onSubmit = async (data: LoginFormValues) => {
    try {
      setServerError(null);
      // GuestOnly redirects once the user is loaded (to the originally requested page if any)
      await login({ username: data.email, password: data.password });
    } catch (error) {
      const status = getErrorStatus(error);
      setServerError(
        t(
          status === 401
            ? 'auth.login.failed'
            : status === 429
              ? 'auth.tooManyAttempts'
              : status === 422
                ? 'auth.validation.checkFields'
                : 'common.errorGeneric',
        ),
      );
    }
  };

  return (
    <AuthShell title={t('auth.login.title')} subtitle={t('auth.login.subtitle')}>
      <form className="space-y-6" onSubmit={handleSubmit(onSubmit)} noValidate>
        {sessionExpired && (
          <div className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
            {t('auth.sessionExpired')}
          </div>
        )}
        <div className="space-y-4">
          <Input
            label={t('auth.fields.email')}
            type="email"
            autoComplete="email"
            dir="ltr"
            required
            {...register('email')}
            error={errors.email?.message && t(errors.email.message)}
          />
          <Input
            label={t('auth.fields.password')}
            type="password"
            autoComplete="current-password"
            dir="ltr"
            required
            {...register('password')}
            error={errors.password?.message && t(errors.password.message)}
          />
        </div>

        {serverError && (
          <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-600">
            {serverError}
          </div>
        )}

        <Button type="submit" className="w-full" isLoading={isSubmitting}>
          {t('auth.login.submit')}
        </Button>

        <p className="text-center text-sm text-gray-600">
          {t('auth.login.noAccount')}{' '}
          <Link to="/register" className="font-medium text-blue-600 hover:text-blue-500">
            {t('auth.login.signUp')}
          </Link>
        </p>
      </form>
    </AuthShell>
  );
};
