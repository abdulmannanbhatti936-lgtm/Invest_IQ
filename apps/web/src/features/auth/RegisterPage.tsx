import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { getErrorStatus, getValidationErrors } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import { useAuth } from './AuthContext';
import { AuthShell } from './AuthShell';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';

// bcrypt (server side) only uses the first 72 bytes of a password; Urdu letters take 2 bytes each
const MAX_PASSWORD_BYTES = 72;
const utf8Bytes = (value: string) => new TextEncoder().encode(value).length;

const registerSchema = z
  .object({
    fullName: z.string().trim().min(2, { message: 'auth.validation.nameMin' }),
    email: z.string().email({ message: 'auth.validation.emailInvalid' }),
    password: z
      .string()
      .min(8, { message: 'auth.validation.passwordMin' })
      .refine((value) => utf8Bytes(value) <= MAX_PASSWORD_BYTES, {
        message: 'auth.validation.passwordTooLong',
      }),
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
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    mode: 'onTouched', // inline errors on blur, then live while correcting (Design.md §12.3)
  });

  const onSubmit = async (data: RegisterFormValues) => {
    try {
      setServerError(null);
      await registerUser({ email: data.email, password: data.password, full_name: data.fullName });
      navigate('/onboarding', { replace: true });
    } catch (error) {
      const status = getErrorStatus(error);
      if (status === 422) {
        // Server-side validation (e.g. the 72-byte password limit): show it on the field
        let placed = false;
        for (const { field } of getValidationErrors(error)) {
          if (field === 'password') {
            setError('password', { message: 'auth.validation.passwordTooLong' });
            placed = true;
          } else if (field === 'email') {
            setError('email', { message: 'auth.validation.emailInvalid' });
            placed = true;
          }
        }
        if (!placed) setServerError(t('auth.validation.checkFields'));
        return;
      }
      setServerError(
        t(
          status === 400
            ? 'auth.register.emailTaken'
            : status === 429
              ? 'auth.tooManyAttempts'
              : 'auth.register.failed',
        ),
      );
    }
  };

  const fieldError = (message?: string) => (message ? t(message) : undefined);

  return (
    <AuthShell
      title={t('auth.register.title')}
      subtitle={t('auth.register.subtitle')}
      showDisclaimer
    >
      <form className="space-y-6" onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="space-y-4">
          <Input
            label={t('auth.fields.fullName')}
            type="text"
            autoComplete="name"
            required
            {...register('fullName')}
            error={fieldError(errors.fullName?.message)}
          />
          <Input
            label={t('auth.fields.email')}
            type="email"
            autoComplete="email"
            dir="ltr"
            required
            {...register('email')}
            error={fieldError(errors.email?.message)}
          />
          <Input
            label={t('auth.fields.password')}
            type="password"
            autoComplete="new-password"
            dir="ltr"
            required
            {...register('password')}
            error={fieldError(errors.password?.message)}
          />
          <Input
            label={t('auth.fields.confirmPassword')}
            type="password"
            autoComplete="new-password"
            dir="ltr"
            required
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
