import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { getErrorMessage, getErrorStatus } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import { useAuth } from './AuthContext';
import { AuthShell } from './AuthShell';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';

const registerSchema = z
  .object({
    fullName: z.string().trim().min(2, { message: 'auth.validation.nameMin' }),
    email: z.string().email({ message: 'auth.validation.emailInvalid' }),
    password: z.string().min(8, { message: 'auth.validation.passwordMin' }),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'auth.validation.passwordsMismatch',
    path: ['confirmPassword'],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

export const RegisterPage = () => {
  const { t } = useTranslation();
  const { register: registerUser } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({ resolver: zodResolver(registerSchema) });

  const onSubmit = async (data: RegisterFormValues) => {
    try {
      setServerError(null);
      await registerUser({ email: data.email, password: data.password, full_name: data.fullName });
      navigate('/onboarding', { replace: true });
    } catch (error) {
      const status = getErrorStatus(error);
      setServerError(
        status === 400
          ? getErrorMessage(error, t('auth.register.failed'))
          : t(status === 429 ? 'auth.tooManyAttempts' : 'auth.register.failed'),
      );
    }
  };

  const fieldError = (message?: string) => (message ? t(message) : undefined);

  return (
    <AuthShell title={t('auth.register.title')} subtitle={t('auth.register.subtitle')}>
      <form className="space-y-6" onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="space-y-4">
          <Input
            label={t('auth.fields.fullName')}
            type="text"
            autoComplete="name"
            {...register('fullName')}
            error={fieldError(errors.fullName?.message)}
          />
          <Input
            label={t('auth.fields.email')}
            type="email"
            autoComplete="email"
            dir="ltr"
            {...register('email')}
            error={fieldError(errors.email?.message)}
          />
          <Input
            label={t('auth.fields.password')}
            type="password"
            autoComplete="new-password"
            dir="ltr"
            {...register('password')}
            error={fieldError(errors.password?.message)}
          />
          <Input
            label={t('auth.fields.confirmPassword')}
            type="password"
            autoComplete="new-password"
            dir="ltr"
            {...register('confirmPassword')}
            error={fieldError(errors.confirmPassword?.message)}
          />
        </div>

        {serverError && (
          <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-600">
            {serverError}
          </div>
        )}

        <Button type="submit" className="w-full" isLoading={isSubmitting}>
          {t('auth.register.submit')}
        </Button>

        <p className="text-center text-sm text-gray-600">
          {t('auth.register.haveAccount')}{' '}
          <Link to="/login" className="font-medium text-blue-600 hover:text-blue-500">
            {t('auth.register.logIn')}
          </Link>
        </p>
      </form>
    </AuthShell>
  );
};
