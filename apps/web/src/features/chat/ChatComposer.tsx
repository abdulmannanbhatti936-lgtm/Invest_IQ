import { useId, type FormEvent, type KeyboardEvent } from 'react';
import { SendHorizontal } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import { Button } from '../../components/ui/Button';
import { ltr } from '../../lib/format';
import { MAX_MESSAGE_CHARS, canSend } from './chatView';

export const ChatComposer = ({
  value,
  onChange,
  onSend,
  sending,
  available,
  waiting,
  inputRef,
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  sending: boolean;
  available: boolean;
  /** Waiting out a provider or message limit: the text stays, sending waits */
  waiting: boolean;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
}) => {
  const { t } = useTranslation();
  const id = useId();
  const hintId = `${id}-hint`;
  const over = value.length > MAX_MESSAGE_CHARS;
  const ready = canSend(value, sending, available, waiting);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (ready) onSend();
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift + Enter keeps a new line. Never while an IME is composing Urdu text
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (ready) onSend();
    }
  };

  return (
    <form onSubmit={submit} className="space-y-2">
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {t('chat.inputLabel')}
      </label>
      <div className="flex items-end gap-2">
        <textarea
          id={id}
          ref={inputRef}
          dir="auto"
          rows={2}
          value={value}
          disabled={!available}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          aria-describedby={hintId}
          aria-invalid={over}
          placeholder={t('chat.inputPlaceholder')}
          className="min-h-[44px] flex-1 resize-y rounded-control border border-line-strong px-4 py-2 text-sm focus:border-primary disabled:bg-sunken"
        />
        <Button type="submit" isLoading={sending} disabled={!ready} aria-label={t('chat.send')}>
          {!sending && <SendHorizontal className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />}
          <span className="ms-2 hidden sm:inline">{t('chat.send')}</span>
        </Button>
      </div>
      <div id={hintId} className="flex justify-between text-xs text-muted">
        <span>{t('chat.keyboardHint')}</span>
        <span className={`tabular-nums ${over ? 'text-danger' : ''}`}>
          {ltr(t('chat.counter', { count: value.length, max: MAX_MESSAGE_CHARS }))}
        </span>
      </div>
    </form>
  );
};
