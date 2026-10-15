import { ARROW, direction } from '../../lib/format';
import { Figure } from './Feedback';

const TONE = { up: 'text-success', down: 'text-danger', flat: 'text-muted' };

/**
 * A gain, loss or no change: arrow plus colour, never colour alone (Design.md §5, §6.3).
 * `value` decides the direction; `children` is the already formatted figure.
 */
export const Delta = ({
  value,
  children,
  className = '',
}: {
  value: number | string | null | undefined;
  children: React.ReactNode;
  className?: string;
}) => {
  const dir = direction(value);
  return (
    <span className={`inline-flex items-baseline gap-2 font-semibold ${TONE[dir]} ${className}`}>
      <span aria-hidden="true">{ARROW[dir]}</span>
      <Figure>{children}</Figure>
    </span>
  );
};
