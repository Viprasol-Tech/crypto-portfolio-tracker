# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[SemVer](https://semver.org/).

## [0.2.0] - 2025

### Added
- **Cost-basis methods**: choose `AVERAGE`, `FIFO`, or `LIFO` lot matching via
  `Portfolio(method=...)`. New `lots.LotBook` engine tracks discrete tax lots.
- **Realized tax-lot report**: `Portfolio.tax_lot_report()` returns per-disposal
  `RealizedSale` rows with proceeds, cost basis, gain/loss, holding period in
  days, and short/long-term classification (>365 days).
- **Allocation & rebalancing** (`analytics`): `allocation()` for market-value
  weights and `rebalance()` for trade suggestions toward a target allocation
  (with a `min_trade` threshold).
- **Performance metrics** (`analytics`): `time_weighted_return()` (flow-aware
  TWR), `max_drawdown()`, and a `performance()` snapshot.
- **CSV import/export** (`io_csv`): `load_transactions`/`save_transactions` plus
  pure `parse_transactions`/`dump_transactions` over a stable schema.
- **CLI subcommands**: `summary`, `taxlots`, `allocation`, `rebalance`,
  `performance`, and `export-sample` alongside the original `demo`/`version`.
- `Portfolio.from_transactions()` and `Portfolio.assets()` helpers.
- New types: `CostBasisMethod`, `RealizedSale`, `AllocationSlice`,
  `RebalanceAction`, `PerformanceSnapshot`; `Transaction.timestamp`.
- Tests expanded from 9 to 63 covering lots, analytics, CSV, methods, and CLI.

### Changed
- `Portfolio` now records realized disposals into `realized_sales` for all
  methods; public PnL APIs are unchanged for average cost.

## [0.1.0] - 2025

### Added
- Initial release of crypto-portfolio-tracker: Crypto portfolio PnL tracker with cost basis (average and realized/unrealized).
