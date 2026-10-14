import { Briefcase, History, LineChart, Newspaper, ShieldCheck, Tag } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import type { ChatMessage, ChatSourceTag } from '@investiq/shared-types';
import { Figure } from '../../components/ui/Feedback';
import { formatDate } from '../../lib/format';
import {
  figureSegments,
  messageDir,
  messageLang,
  replyDisclaimerKey,
  sourceTag,
  uniqueSources,
} from './chatView';

const SOURCE_ICONS = {
  portfolio: Briefcase,
  prediction: LineChart,
  sentiment: Newspaper,
  backtest: History,
  price: Tag,
  risk_profile: ShieldCheck,
} as const;

/** Reply text with every figure kept left to right, even inside an Urdu sentence. */
export const MessageText = ({ text }: { text: string }) => (
  <>
    {figureSegments(text).map((segment, i) =>
      segment.figure ? (
        <Figure key={i}>{segment.text}</Figure>
      ) : (
        <span key={i}>{segment.text}</span>
      ),
    )}
  </>
);

const SourceTags = ({ sources }: { sources: ChatSourceTag[] }) => {
  const { t, i18n } = useTranslation();
  const tags = uniqueSources(sources);
  if (tags.length === 0) return null;
  return (
    <ul aria-label={t('chat.sourcesLabel')} className="mt-2 flex flex-wrap gap-2">
      {tags.map((tag) => {
        const Icon = SOURCE_ICONS[tag.kind];
        const { key, params } = sourceTag(tag);
        const date = params.date ? formatDate(params.date, i18n.language) : '';
        return (
          <li
            key={`${tag.kind}:${tag.ticker ?? ''}`}
            className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-2 text-xs text-muted"
          >
            <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
            {t(key, { ...params, date })}
          </li>
        );
      })}
    </ul>
  );
};

/**
 * One message (Design.md §6.5): the user's on the end side in the primary colour, the
 * assistant's on the start side on the surface colour with its data-source tags. Bubbles use
 * logical sides, so in Urdu (right to left) the user's sit on the left.
 */
export const MessageBubble = ({ message }: { message: ChatMessage }) => {
  const { t, i18n } = useTranslation();
  const mine = message.role === 'user';
  const disclaimer = mine ? null : replyDisclaimerKey(message.language, i18n.language);
  return (
    <li className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className="max-w-[85%] sm:max-w-[75%]">
        <span className="sr-only">{mine ? t('chat.you') : t('chat.assistant')}</span>
        <div
          dir={messageDir(message.language)}
          lang={messageLang(message.language)}
          className={`whitespace-pre-line rounded-2xl px-4 py-4 text-sm leading-relaxed ${
            mine
              ? 'rounded-ee-sm bg-primary text-inverse'
              : 'rounded-es-sm border border-line bg-sunken text-ink'
          }`}
        >
          <MessageText text={message.content} />
        </div>
        {!mine && <SourceTags sources={message.sources} />}
        {disclaimer && (
          <p
            dir={messageDir(message.language)}
            lang={messageLang(message.language)}
            className="mt-2 text-sm text-muted"
          >
            {t(disclaimer.key, disclaimer.lng ? { lng: disclaimer.lng } : undefined)}
          </p>
        )}
      </div>
    </li>
  );
};
