// "What it really costs": the Phase 5 hand-worked example (DetailedReport.md, Phase 5), Rs 100,000,
// Moderate, filer, prices of the 7 Oct 2026 close, rates psx-costs-2026-10-11.2. Each line is
// the sum of that column over the eight holdings, exactly as the cost engine's fixtures
// (tests/test_cost_engine.py) give them; nothing is recalculated here.
export const COST_EXAMPLE = {
  pricesDate: '2026-10-07',
  ratesVersion: 'psx-costs-2026-10-11.2',
  capital: '100000.00',
  shares: '99706.41',
  charges: [
    { key: 'commission', amount: '149.55' },
    { key: 'sales_tax', amount: '22.43' },
    { key: 'cdc_fee', amount: '3.59' },
    { key: 'psx_trading_fee', amount: '3.48' },
    { key: 'secp_levy', amount: '0.66' },
    { key: 'nccpl_trade_fee', amount: '0.80' },
    { key: 'nccpl_secp_fee', amount: '0.29' },
  ],
  chargesTotal: '180.80',
  cash: '112.79',
} as const;
