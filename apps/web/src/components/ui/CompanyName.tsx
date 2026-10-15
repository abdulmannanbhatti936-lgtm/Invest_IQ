/**
 * An English company name (or sector) inside any layout: always left to right, so in Urdu it is
 * never cut from the left; truncated at its end with an ellipsis, and the full name on hover or
 * long-press (Design.md §24; RTL bug found 2026-10-13, Memory.md §4).
 */
export const CompanyName = ({ name, className = '' }: { name: string; className?: string }) => (
  <span dir="ltr" title={name} className={`iq-truncate-end min-w-0 ${className}`}>
    {name}
  </span>
);
