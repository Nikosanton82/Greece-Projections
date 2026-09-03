# Greece Macro Projections: Data Dictionary

Retrieved 2026-09-03. All series are annual, Greece (EL/GRC), 1995-2025 unless stated. The tidy file `data/2026-09-03-greece-macro-tidy.csv` carries one row per (variable, year) with `source`, `dataset`, `vintage`, `kind`. Official institutional forecasts are in `data/2026-09-03-official-projections.csv` with an `entry_method` column (`api` = pulled programmatically, `manual` = transcribed from a PDF).

## Sources and vintages

| Source | Access | Vintage used | Notes |
|---|---|---|---|
| Eurostat | REST API `api/dissemination/statistics/1.0` (JSON-stat) | Database as of 2026-09-02 (national accounts 2025 provisional released that day) | Primary source for history |
| IMF World Economic Outlook | DataMapper API `imf.org/external/datamapper/api/v1` | April 2026 WEO | Projections 2026-2031; also history where Eurostat is short (unemployment pre-2009, current account BoP basis, GDP per capita PPP) |
| European Commission AMECO | via DBnomics `api.db.nomics.world/v22/series/AMECO` | Spring 2026 Forecast vintage | TFP, potential GDP, output gap, NAWRU, net capital stock; EC forecasts 2026-2027 |
| OECD Economic Outlook | SDMX API `sdmx.oecd.org` dataflow `OECD.ECO.MAD/DSD_EO@DF_EO` | EO 119 (June 2026) | Projections 2026-2027 |
| Bank of Greece | PDF, Note on the Greek Economy 17 July 2026 | June 2026 Monetary Policy Report | Manual entry, 2026-2028 |
| Ministry of Finance | PDFs: Annual Progress Report (Apr 2026), Draft Budgetary Plan 2026 (Oct 2025), Medium-Term Fiscal-Structural Plan 2025-28 (Oct 2024) | see file | Manual entry; the MTFSP gives the official debt path to 2038 |
| Eurostat EUROPOP2023 | REST API `proj_23np`, `proj_23ndbi`, `proj_23naasfr` | 2023 projection round | Population, old-age dependency, assumed TFR (sum of assumed age-specific rates) |

## Variables (history file)

| variable | unit | Eurostat/other code | Comment |
|---|---|---|---|
| gdp_nominal_bn_eur | bn EUR, current prices | nama_10_gdp B1GQ CP_MEUR | |
| gdp_real_bn_eur2015 | bn EUR, chain-linked 2015 | nama_10_gdp B1GQ CLV15_MEUR | |
| gdp_growth | % | computed from CLV15 | 1996-2025 |
| gdp_pc_nominal_eur | EUR per head | nama_10_pc CP_EUR_HAB | |
| gdp_pc_real_eur2015 | EUR per head, 2015 prices | nama_10_pc CLV15_EUR_HAB | |
| gdp_pc_pps | PPS (EU27_2020) per head | nama_10_pc CP_PPS_EU27_2020_HAB | for EU convergence comparisons |
| gdp_pc_ppp_usd | intl $ per head | IMF WEO PPPPC | history and IMF projection on the same basis |
| gdp_deflator_growth | % | nama_10_gdp PD_PCH_PRE_NAC | |
| hicp_inflation | % annual average | prc_hicp_aind CP00 RCH_A_AVG | 1996-2025 |
| unemployment_rate | % of labour force, 15-74 | une_rt_a; IMF LUR spliced 1995-2008 | |
| employment_rate_20_64 | % of population 20-64 | lfsi_emp_a | 2009-2025 (LFS break) |
| activity_rate_15_64 | % | lfsa_argan | |
| employment_ths_persons | thousand persons, domestic concept | nama_10_a10_e EMP_DC | |
| hours_worked_mn | million hours | nama_10_a10_e EMP_DC THS_HW /1000 | |
| labour_productivity_per_hour_idx | 2015=100 | nama_10_lp_ulc RLPR_HW | |
| ulc_growth | % | nama_10_lp_ulc NULC_PER PCH_PRE | nominal ULC per person |
| investment_pct_gdp | % of GDP, current prices | P51G/B1GQ | |
| investment_growth | % | P51G CLV15 computed | |
| exports_pct_gdp | % of GDP | P6/B1GQ | |
| current_account_pct_gdp | % of GDP | IMF WEO BCA_NGDPD | BoP basis |
| niip_pct_gdp | % of GDP | tipsii40 Q4 | 2003-2025 |
| reer_cpi_ic42 | 2015=100 | ert_eff_ic_a REER_IC42_CPI | vs 42 trading partners |
| reer_ulc_ea20 | 2015=100 | ert_eff_ic_a REER_EA20_ULCT | ULC-based vs euro area |
| public_debt_pct_gdp | % of GDP | gov_10dd_edpt1 GD S13 | Maastricht definition |
| gg_balance_pct_gdp | % of GDP | gov_10dd_edpt1 B9 S13 | |
| gg_interest_pct_gdp | % of GDP | gov_10a_main D41PAY | |
| primary_balance_pct_gdp | % of GDP | B9 + D41PAY computed | |
| gg_revenue_pct_gdp, gg_expenditure_pct_gdp | % of GDP | gov_10a_main TR, TE | |
| bond_yield_10y | % | irt_lt_mcby_a | Maastricht long-term yield |
| private_debt_pct_gdp | % of GDP | tipspd20 | NFC + households, consolidated, loans and debt securities (MIP headline) |
| household_debt_pct_gdp | % of GDP | tipspd22 | |
| nfc_debt_pct_gdp | % of GDP | tipspd20 minus tipspd22 | |
| household_saving_rate | % of gross disposable income | nasa_10_ki SRG_S14_S15 | to 2024 |
| tfp_idx_2020 | 2020=100 | AMECO ZVGDF | EC production-function TFP |
| tfp_growth | % | computed from ZVGDF | |
| tfp_solow_idx_2020 | 2020=100 | computed | Solow residual with alpha=0.35, Eurostat real GDP and hours, AMECO net capital stock; replicates AMECO to three decimals, which confirms the EC uses the same inputs and share |
| potential_gdp_bn_eur2020, potential_growth, output_gap, nawru | bn EUR / % / % of potential / % | AMECO OVGDP, AVGDGP, ZNAWRU | EC Output Gap Working Group method |
| capital_stock_bn_eur2020 | bn EUR 2020 prices | AMECO OKND | net capital stock, total economy |
| fertility_rate | children per woman | demo_find TOTFERRT | 1990-2024 (2025 not yet published) |
| population_mn | million, 1 January | demo_gind JAN | 1995-2026 |
| net_migration_ths | thousand | demo_gind CNMIGRAT | includes statistical adjustment |
| natural_change_ths | thousand | demo_gind NATGROW | |
| old_age_dependency | % (65+ / 15-64) | demo_pjanind OLDDEP1 | |
| median_age | years | demo_pjanind MEDAGEPOP | |

## Known caveats

Eurostat 2025 national-accounts values are first provisional estimates (released 2026-09-02) and will be revised in October 2026 with the EDP notification. The OECD series `gg_gross_financial_liabilities_pct_gdp` uses the SNA definition and is about 15-20 points above Maastricht debt; it is kept for reference only and not compared with the debt fan chart. Bank of Greece and Ministry of Finance projections were transcribed by hand from PDFs and should be spot-checked against the originals before publication. The EUROPOP2023 fertility assumption (1.42 in 2025) is already above the 2024 outturn (1.24), so the Eurostat population baseline is optimistic relative to recent data. The Eurostat unemployment series starts in 2009 because of the LFS methodological break; the spliced IMF values for 1995-2008 are on the older LFS basis.
