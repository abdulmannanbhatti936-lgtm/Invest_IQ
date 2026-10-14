import { useCallback, useEffect, useRef, useState } from 'react';
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query';
import { MessageSquare, Trash2 } from 'lucide-react';
import { chatApi, getErrorDetail, getErrorStatus } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { ChatHistory, SendChatMessageResponse } from '@investiq/shared-types';
import { LanguageToggle } from '../../components/LanguageToggle';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { DisclaimerBanner, ErrorState, Notice, Skeleton } from '../../components/ui/Feedback';
import { ChatComposer } from './ChatComposer';
import { MessageBubble, MessageText } from './MessageBubble';
import { conversation, secondsLeft, sendProblem, type SendProblem } from './chatView';

const HISTORY_KEY = ['chat', 'history'] as const;
const STARTERS = ['portfolio', 'lowConfidence', 'sentiment', 'backtest'] as const;

type History = InfiniteData<ChatHistory, string | null>;

const TypingIndicator = () => {
  const { t } = useTranslation();
  return (
    <li className="flex justify-start" role="status">
      <span className="sr-only">{t('chat.typing')}</span>
      <div
        className="flex gap-2 rounded-2xl rounded-es-sm border border-line bg-sunken px-4 py-4"
        aria-hidden="true"
      >
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="h-2 w-2 animate-pulse rounded-full bg-muted motion-reduce:animate-none"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </li>
  );
};

/**
 * A live countdown from the API's wait (Retry-After). The number changes every second but only
 * the start and the "you can send now" line are announced, so screen readers are not flooded.
 */
const Countdown = ({
  until,
  messageKey,
  onDone,
}: {
  until: number;
  messageKey: string;
  onDone: () => void;
}) => {
  const { t } = useTranslation();
  const [now, setNow] = useState(() => Date.now());
  const [announced] = useState(() => secondsLeft(until, Date.now()));
  const left = secondsLeft(until, now);
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(id);
  }, []);
  useEffect(() => {
    if (left === 0) onDone();
  }, [left, onDone]);
  return (
    <Notice tone="warning">
      <span role="status" className="sr-only">
        {t(messageKey, { seconds: announced })}
      </span>
      <span aria-hidden="true" className="tabular-nums">
        {t(messageKey, { seconds: left })}
      </span>
    </Notice>
  );
};

const SendError = ({
  problem,
  waitUntil,
  onWaitOver,
  onRetry,
}: {
  problem: SendProblem;
  waitUntil: number | null;
  onWaitOver: () => void;
  onRetry: () => void;
}) => {
  const { t } = useTranslation();
  const waits = problem.kind === 'rateLimited' || problem.kind === 'busy';
  if (waits && problem.seconds != null) {
    if (waitUntil == null)
      return (
        <p role="status" className="text-sm text-muted">
          {t('chat.error.ready')}
        </p>
      );
    return (
      <Countdown
        until={waitUntil}
        messageKey={problem.kind === 'busy' ? 'chat.error.busyCountdown' : 'chat.error.rateLimited'}
        onDone={onWaitOver}
      />
    );
  }
  if (problem.kind === 'rateLimited')
    return <Notice tone="warning">{t('chat.error.rateLimitedLater')}</Notice>;
  return (
    <ErrorState
      message={problem.kind === 'busy' ? t('chat.error.busy') : t('chat.error.failed')}
      onRetry={onRetry}
    />
  );
};

const ClearHistory = ({ onConfirm, clearing }: { onConfirm: () => void; clearing: boolean }) => {
  const { t } = useTranslation();
  const [confirming, setConfirming] = useState(false);
  if (!confirming)
    return (
      <Button variant="secondary" onClick={() => setConfirming(true)}>
        <Trash2 className="me-2 h-4 w-4" aria-hidden="true" />
        {t('chat.clear')}
      </Button>
    );
  return (
    <div role="group" aria-label={t('chat.clear')} className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-ink">{t('chat.clearConfirm')}</span>
      <Button variant="destructive" isLoading={clearing} onClick={onConfirm}>
        {t('chat.clearYes')}
      </Button>
      <Button variant="secondary" onClick={() => setConfirming(false)} disabled={clearing}>
        {t('chat.clearNo')}
      </Button>
    </div>
  );
};

export const ChatPage = () => {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLLIElement>(null);
  const [draft, setDraft] = useState('');
  const [failed, setFailed] = useState<{ content: string; problem: SendProblem } | null>(null);
  const [waitUntil, setWaitUntil] = useState<number | null>(null);
  const [unconfigured, setUnconfigured] = useState(false);
  const endWait = useCallback(() => setWaitUntil(null), []);

  const history = useInfiniteQuery({
    queryKey: HISTORY_KEY,
    queryFn: ({ pageParam }) => chatApi.history(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_before,
  });

  const send = useMutation({
    mutationFn: (content: string) =>
      chatApi.send({ content, language: i18n.language === 'ur' ? 'ur' : 'en' }),
    onMutate: () => {
      setFailed(null);
      setWaitUntil(null);
    },
    onSuccess: (result: SendChatMessageResponse) => {
      queryClient.setQueryData<History>(HISTORY_KEY, (data) =>
        data
          ? {
              ...data,
              pages: data.pages.map((page, i) =>
                i === 0
                  ? { ...page, messages: [result.reply, result.user_message, ...page.messages] }
                  : page,
              ),
            }
          : data,
      );
      inputRef.current?.focus();
    },
    onError: (error, content) => {
      const problem = sendProblem(getErrorStatus(error), getErrorDetail(error));
      if (problem.kind === 'unavailable') setUnconfigured(true);
      if ((problem.kind === 'busy' || problem.kind === 'rateLimited') && problem.seconds != null)
        setWaitUntil(Date.now() + problem.seconds * 1000);
      setFailed({ content, problem });
      // The message stays in the box, ready to send again
      setDraft((current) => current || content);
    },
  });

  const clear = useMutation({
    mutationFn: chatApi.clear,
    onSuccess: () => {
      setFailed(null);
      void queryClient.resetQueries({ queryKey: HISTORY_KEY });
    },
  });

  const messages = conversation(history.data?.pages ?? []);
  const available = !unconfigured && (history.data?.pages[0]?.chat_available ?? true);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [messages.length, send.isPending]);

  const submit = (content: string) => {
    setDraft('');
    send.mutate(content.trim());
  };

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">{t('chat.title')}</h1>
          <p className="mt-2 text-sm text-muted">{t('chat.subtitle')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <LanguageToggle className="border border-line" />
          {messages.length > 0 && (
            <ClearHistory onConfirm={() => clear.mutate()} clearing={clear.isPending} />
          )}
        </div>
      </div>

      {clear.isError && <Notice tone="warning">{t('chat.clearError')}</Notice>}

      {!available && (
        <Notice tone="warning">
          <p className="font-medium">{t('chat.unavailable.title')}</p>
          <p className="mt-2">{t('chat.unavailable.body')}</p>
        </Notice>
      )}

      <Card className="flex flex-col gap-4 p-4 sm:p-6">
        {history.isPending && (
          <div className="space-y-4" aria-busy="true">
            <Skeleton className="ms-auto h-10 w-1/2" />
            <Skeleton className="h-20 w-3/4" />
            <Skeleton className="ms-auto h-10 w-2/5" />
          </div>
        )}

        {history.isError && (
          <ErrorState message={t('chat.loadError')} onRetry={() => void history.refetch()} />
        )}

        {history.isSuccess && messages.length === 0 && !send.isPending && (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <MessageSquare className="h-8 w-8 text-muted" aria-hidden="true" />
            <div>
              <p className="font-medium text-ink">{t('chat.empty.title')}</p>
              <p className="mt-2 text-sm text-muted">{t('chat.empty.body')}</p>
            </div>
            <ul className="flex w-full flex-col gap-2 sm:max-w-md">
              {STARTERS.map((key) => (
                <li key={key}>
                  <button
                    type="button"
                    disabled={!available}
                    onClick={() => submit(t(`chat.starters.${key}`))}
                    className="w-full rounded-control border border-line px-4 py-4 text-start text-sm text-ink transition-colors hover:bg-sunken disabled:opacity-50"
                  >
                    {t(`chat.starters.${key}`)}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {history.hasNextPage && (
          <div className="flex justify-center">
            <Button
              variant="secondary"
              isLoading={history.isFetchingNextPage}
              onClick={() => void history.fetchNextPage()}
            >
              {t('chat.loadOlder')}
            </Button>
          </div>
        )}

        {(messages.length > 0 || send.isPending || failed) && (
          <ol
            role="log"
            aria-live="polite"
            aria-relevant="additions"
            className="flex flex-col gap-4"
          >
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {send.isPending && send.variables && (
              <>
                <li className="flex justify-end">
                  <div
                    className="max-w-[85%] whitespace-pre-line rounded-2xl rounded-ee-sm bg-primary px-4 py-4 text-sm text-inverse opacity-80 sm:max-w-[75%]"
                    dir="auto"
                  >
                    <span className="sr-only">{t('chat.you')}</span>
                    <MessageText text={send.variables} />
                  </div>
                </li>
                <TypingIndicator />
              </>
            )}
            <li ref={endRef} aria-hidden="true" />
          </ol>
        )}

        {failed && (
          <SendError
            problem={failed.problem}
            waitUntil={waitUntil}
            onWaitOver={endWait}
            onRetry={() => submit(failed.content)}
          />
        )}

        <p className="text-xs text-muted">{t('chat.privacy')}</p>
        <ChatComposer
          value={draft}
          onChange={setDraft}
          onSend={() => submit(draft)}
          sending={send.isPending}
          available={available}
          waiting={waitUntil != null}
          inputRef={inputRef}
        />
      </Card>

      <DisclaimerBanner />
    </div>
  );
};
