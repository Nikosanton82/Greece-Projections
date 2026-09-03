"""
2026-09-03-build-dataset.py
Assemble a tidy, long-format panel of Greek macro series from the raw API snapshots in data/raw/.
Output: data/2026-09-03-greece-macro-tidy.csv  (columns: variable, year, value, source, dataset, vintage, kind)
        data/2026-09-03-greece-macro-wide.csv  (one column per variable, history only)
        data/2026-09-03-official-projections.csv (institution, variable, year, value, vintage)

kind = "history" for outturns, "projection" for official institutional forecasts.
Re-run after refreshing data/raw/ with 2026-09-03-fetch-data.py.
"""
import json, os, sys
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
OUT = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)
LAST_HIST = 2025  # last outturn year available (Eurostat provisional 2025 released 2026-09-02)

def load(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return json.load(f)

rows = []
def add(variable, series, source, dataset, vintage, kind="history", first=1995, last=None):
    for y, v in series.items():
        y = int(y)
        if v is None or y < first: continue
        if last is not None and y > last: continue
        rows.append(dict(variable=variable, year=y, value=float(v), source=source, dataset=dataset, vintage=vintage, kind=kind))

# ---------------- Eurostat (history) ----------------
e1 = load("eurostat_batch1.json"); e2 = load("eurostat_batch2.json"); e3 = load("eurostat_batch3.json")
ES = "Eurostat"
s = e1["nama_10_gdp_lvl"]["series"]
add("gdp_nominal_bn_eur", {y: v/1000 for y, v in s["B1GQ|CP_MEUR"].items()}, ES, "nama_10_gdp B1GQ CP_MEUR", e1["nama_10_gdp_lvl"]["updated"])
add("gdp_real_bn_eur2015", {y: v/1000 for y, v in s["B1GQ|CLV15_MEUR"].items()}, ES, "nama_10_gdp B1GQ CLV15_MEUR", e1["nama_10_gdp_lvl"]["updated"])
real = pd.Series({int(y): v for y, v in s["B1GQ|CLV15_MEUR"].items()}).sort_index()
add("gdp_growth", (real.pct_change()*100).dropna().round(2).to_dict(), ES, "nama_10_gdp B1GQ CLV15_MEUR (computed % change)", e1["nama_10_gdp_lvl"]["updated"], first=1996)
nom = pd.Series({int(y): v for y, v in s["B1GQ|CP_MEUR"].items()}).sort_index()
add("investment_pct_gdp", (pd.Series({int(y): v for y, v in s["P51G|CP_MEUR"].items()})/nom*100).round(2).to_dict(), ES, "nama_10_gdp P51G/B1GQ CP_MEUR", e1["nama_10_gdp_lvl"]["updated"])
inv_real = pd.Series({int(y): v for y, v in s["P51G|CLV15_MEUR"].items()}).sort_index()
add("investment_real_bn_eur2015", (inv_real/1000).round(4).to_dict(), ES, "nama_10_gdp P51G CLV15_MEUR", e1["nama_10_gdp_lvl"]["updated"])
add("investment_growth", (inv_real.pct_change()*100).dropna().round(2).to_dict(), ES, "nama_10_gdp P51G CLV15_MEUR (computed % change)", e1["nama_10_gdp_lvl"]["updated"], first=1996)
add("exports_pct_gdp", (pd.Series({int(y): v for y, v in s["P6|CP_MEUR"].items()})/nom*100).round(2).to_dict(), ES, "nama_10_gdp P6/B1GQ", e1["nama_10_gdp_lvl"]["updated"])
add("gdp_deflator_growth", e1["nama_10_gdp_defl"]["series"]["B1GQ|PD_PCH_PRE_NAC"], ES, "nama_10_gdp PD_PCH_PRE_NAC", e1["nama_10_gdp_defl"]["updated"])
pc = e1["nama_10_pc"]["series"]
add("gdp_pc_nominal_eur", pc["B1GQ|CP_EUR_HAB"], ES, "nama_10_pc CP_EUR_HAB", e1["nama_10_pc"]["updated"])
add("gdp_pc_real_eur2015", pc["B1GQ|CLV15_EUR_HAB"], ES, "nama_10_pc CLV15_EUR_HAB", e1["nama_10_pc"]["updated"])
add("gdp_pc_pps", pc["B1GQ|CP_PPS_EU27_2020_HAB"], ES, "nama_10_pc CP_PPS_EU27_2020_HAB", e1["nama_10_pc"]["updated"])
add("hicp_inflation", e1["prc_hicp_aind"]["series"]["CP00|RCH_A_AVG"], ES, "prc_hicp_aind CP00 RCH_A_AVG", e1["prc_hicp_aind"]["updated"])
add("gg_balance_pct_gdp", e1["gov_10dd_edpt1"]["series"]["B9|S13|PC_GDP"], ES, "gov_10dd_edpt1 B9 S13", e1["gov_10dd_edpt1"]["updated"])
add("public_debt_pct_gdp", e1["gov_10dd_edpt1"]["series"]["GD|S13|PC_GDP"], ES, "gov_10dd_edpt1 GD S13 (Maastricht)", e1["gov_10dd_edpt1"]["updated"])
add("gg_interest_pct_gdp", e1["gov_10a_main"]["series"]["D41PAY|S13|PC_GDP"], ES, "gov_10a_main D41PAY S13", e1["gov_10a_main"]["updated"])
add("gg_revenue_pct_gdp", e1["gov_10a_main"]["series"]["TR|S13|PC_GDP"], ES, "gov_10a_main TR S13", e1["gov_10a_main"]["updated"])
add("gg_expenditure_pct_gdp", e1["gov_10a_main"]["series"]["TE|S13|PC_GDP"], ES, "gov_10a_main TE S13", e1["gov_10a_main"]["updated"])
bal = pd.Series({int(y): v for y, v in e1["gov_10dd_edpt1"]["series"]["B9|S13|PC_GDP"].items()})
intr = pd.Series({int(y): v for y, v in e1["gov_10a_main"]["series"]["D41PAY|S13|PC_GDP"].items()})
add("primary_balance_pct_gdp", (bal+intr).dropna().round(2).to_dict(), ES, "gov_10dd_edpt1 B9 + gov_10a_main D41PAY (computed)", e1["gov_10a_main"]["updated"])

add("fertility_rate", e2["demo_find"]["series"]["TOTFERRT"], ES, "demo_find TOTFERRT", e2["demo_find"]["updated"], first=1990)
g = e2["demo_gind"]["series"]
add("population_mn", {y: v/1e6 for y, v in g["JAN"].items()}, ES, "demo_gind JAN (1 January)", e2["demo_gind"]["updated"])
add("net_migration_ths", {y: v/1000 for y, v in g["CNMIGRAT"].items()}, ES, "demo_gind CNMIGRAT (incl. statistical adjustment)", e2["demo_gind"]["updated"])
add("natural_change_ths", {y: v/1000 for y, v in g["NATGROW"].items()}, ES, "demo_gind NATGROW", e2["demo_gind"]["updated"])
add("old_age_dependency", e2["demo_pjanind"]["series"]["OLDDEP1"], ES, "demo_pjanind OLDDEP1 (65+/15-64)", e2["demo_pjanind"]["updated"])
add("median_age", e2["demo_pjanind"]["series"]["MEDAGEPOP"], ES, "demo_pjanind MEDAGEPOP", e2["demo_pjanind"]["updated"])
add("private_debt_pct_gdp", e2["tipspd20"]["series"]["F3_F4|LIAB|S11_S14_S15|CO|PC_GDP"], ES, "tipspd20 (NFC+HH, consolidated, loans+debt securities)", e2["tipspd20"]["updated"])
add("household_debt_pct_gdp", e3["tipspd22"]["series"]["F3_F4|LIAB|S14_S15|CO|PC_GDP"], ES, "tipspd22 (HH+NPISH consolidated)", e3["tipspd22"]["updated"])
pd_ = pd.Series({int(y): v for y, v in e2["tipspd20"]["series"]["F3_F4|LIAB|S11_S14_S15|CO|PC_GDP"].items()})
hh = pd.Series({int(y): v for y, v in e3["tipspd22"]["series"]["F3_F4|LIAB|S14_S15|CO|PC_GDP"].items()})
add("nfc_debt_pct_gdp", (pd_-hh).dropna().round(1).to_dict(), ES, "tipspd20 minus tipspd22 (computed)", e2["tipspd20"]["updated"])
add("employment_rate_20_64", e2["lfsi_emp_a"]["series"]["PC_POP|Y20-64|T|EMP_LFS"], ES, "lfsi_emp_a EMP_LFS 20-64", e2["lfsi_emp_a"]["updated"])
add("activity_rate_15_64", e2["lfsa_argan"]["series"]["TOTAL|Y15-64|T|PC"], ES, "lfsa_argan 15-64", e2["lfsa_argan"]["updated"])
add("employment_ths_persons", e2["nama_10_a10_e"]["series"]["EMP_DC|TOTAL|THS_PER"], ES, "nama_10_a10_e EMP_DC THS_PER", e2["nama_10_a10_e"]["updated"])
add("hours_worked_mn", {y: v/1000 for y, v in e2["nama_10_a10_e"]["series"]["EMP_DC|TOTAL|THS_HW"].items()}, ES, "nama_10_a10_e EMP_DC THS_HW", e2["nama_10_a10_e"]["updated"])
add("labour_productivity_per_hour_idx", e2["nama_10_lp_ulc"]["series"]["RLPR_HW|I15"], ES, "nama_10_lp_ulc RLPR_HW I15", e2["nama_10_lp_ulc"]["updated"])
add("ulc_growth", e2["nama_10_lp_ulc"]["series"]["NULC_PER|PCH_PRE"], ES, "nama_10_lp_ulc NULC_PER PCH_PRE", e2["nama_10_lp_ulc"]["updated"])
add("reer_cpi_ic42", e2["ert_eff_ic_a"]["series"]["I15|REER_IC42_CPI"], ES, "ert_eff_ic_a REER_IC42_CPI (2015=100)", e2["ert_eff_ic_a"]["updated"])
add("reer_ulc_ea20", e2["ert_eff_ic_a"]["series"]["I15|REER_EA20_ULCT"], ES, "ert_eff_ic_a REER_EA20_ULCT (2015=100)", e2["ert_eff_ic_a"]["updated"])
add("bond_yield_10y", e3["irt_lt_mcby_a"]["series"]["MCBY"], ES, "irt_lt_mcby_a (Maastricht criterion yield)", e3["irt_lt_mcby_a"]["updated"])
add("niip_pct_gdp", e3["tipsii40_niip_q4"]["series"]["NIIP_PC_GDP"], ES, "tipsii40 (Q4)", e3["tipsii40_niip_q4"]["updated"])
add("household_saving_rate", e3["nasa_10_ki"]["series"]["S14_S15|SRG_S14_S15|PC"], ES, "nasa_10_ki SRG_S14_S15", e3["nasa_10_ki"]["updated"])

# Unemployment: Eurostat une_rt_a only from 2009; splice IMF WEO (identical definition, LFS) for 1995-2008
imf = load("imf_weo_apr2026_GRC.json")
add("unemployment_rate", e1["une_rt_a"]["series"]["T|PC_ACT|Y15-74"], ES, "une_rt_a 15-74", e1["une_rt_a"]["updated"])
add("unemployment_rate", {y: v for y, v in imf["LUR"].items() if int(y) < 2009}, "IMF WEO", "LUR (spliced for 1995-2008)", imf["vintage"])
# Current account: IMF WEO (BoP basis) for history
add("current_account_pct_gdp", imf["BCA_NGDPD"], "IMF WEO", "BCA_NGDPD", imf["vintage"], last=LAST_HIST)
add("gdp_pc_ppp_usd", imf["PPPPC"], "IMF WEO", "PPPPC (intl $)", imf["vintage"], last=LAST_HIST)

# ---------------- AMECO (history + EC 2026-27) ----------------
am = load("ameco_dbnomics_GRC.json")
AM = "AMECO (EC, Spring 2026)"
add("tfp_idx_2020", am["ZVGDF"]["data"], AM, "ZVGDF", "Spring 2026", last=LAST_HIST)
tfp = pd.Series({int(y): v for y, v in am["ZVGDF"]["data"].items()}).sort_index()
add("tfp_growth", (tfp.pct_change()*100).dropna().round(2).to_dict(), AM, "ZVGDF (computed % change)", "Spring 2026", first=1996, last=LAST_HIST)
add("potential_gdp_bn_eur2020", am["OVGDP"]["data"], AM, "OVGDP", "Spring 2026", last=LAST_HIST)
pot = pd.Series({int(y): v for y, v in am["OVGDP"]["data"].items()}).sort_index()
add("potential_growth", (pot.pct_change()*100).dropna().round(2).to_dict(), AM, "OVGDP (computed % change)", "Spring 2026", first=1996, last=LAST_HIST)
add("output_gap", am["AVGDGP"]["data"], AM, "AVGDGP", "Spring 2026", last=LAST_HIST)
add("nawru", am["ZNAWRU"]["data"], AM, "ZNAWRU", "Spring 2026", last=LAST_HIST)
add("capital_stock_bn_eur2020", am["OKND"]["data"], AM, "OKND", "Spring 2026", last=LAST_HIST)

hist = pd.DataFrame(rows)

# ---------------- Own Solow-residual TFP (cross-check of AMECO) ----------------
# ln A = ln Y - a ln K - (1-a) ln H, a = 0.35 (EC OGWG convention: labour share 0.65)
w = hist.pivot_table(index="year", columns="variable", values="value", aggfunc="first")
if all(c in w for c in ["gdp_real_bn_eur2015", "capital_stock_bn_eur2020", "hours_worked_mn"]):
    a = 0.35
    lnA = np.log(w["gdp_real_bn_eur2015"]) - a*np.log(w["capital_stock_bn_eur2020"]) - (1-a)*np.log(w["hours_worked_mn"])
    A = np.exp(lnA - lnA.loc[2020]) * 100
    add("tfp_solow_idx_2020", A.dropna().round(3).to_dict(), "Computed", "Solow residual, alpha=0.35, Eurostat Y & hours, AMECO K", "2026-09-03")
    hist = pd.DataFrame(rows)

# ---------------- Official projections ----------------
proj = []
def addp(inst, variable, series, vintage, first=2026, entry="api"):
    for y, v in series.items():
        if int(y) >= first and v is not None:
            proj.append(dict(institution=inst, variable=variable, year=int(y), value=float(v), vintage=vintage, entry_method=entry))

# IMF WEO April 2026 (2026-2031)
V = imf["vintage"]
addp("IMF WEO", "gdp_growth", imf["NGDP_RPCH"], V)
addp("IMF WEO", "hicp_inflation", imf["PCPIPCH"], V)
addp("IMF WEO", "unemployment_rate", imf["LUR"], V)
addp("IMF WEO", "public_debt_pct_gdp", imf["GGXWDG_NGDP"], V)
addp("IMF WEO", "gg_balance_pct_gdp", imf["GGXCNL_NGDP"], V)
addp("IMF WEO", "current_account_pct_gdp", imf["BCA_NGDPD"], V)
addp("IMF WEO", "gdp_pc_ppp_usd", imf["PPPPC"], V)
addp("IMF WEO", "population_mn", imf["LP"], V)

# EC Spring 2026 (2026-2027) from AMECO
ec = load("ec_spring2026_forecast_GRC.json")
V = "EC Spring 2026"
rg = pd.Series({int(y): v for y, v in ec["OVGD_real_gdp_bn2020"].items()}).sort_index()
addp("European Commission", "gdp_growth", (rg.pct_change()*100).round(2).to_dict(), V)
hi = pd.Series({int(y): v for y, v in ec["ZCPIH_hicp_index_2015"].items()}).sort_index()
addp("European Commission", "hicp_inflation", (hi.pct_change()*100).round(2).to_dict(), V)
addp("European Commission", "unemployment_rate", ec["ZUTN_unemployment_rate"], V)
addp("European Commission", "public_debt_pct_gdp", ec["UDGG_debt_pct_gdp"], V)
addp("European Commission", "gg_balance_pct_gdp", ec["UBLG_balance_pct_gdp"], V)
addp("European Commission", "primary_balance_pct_gdp", ec["UBLGI_primary_balance_pct_gdp"], V)
addp("European Commission", "current_account_pct_gdp", ec["UBCA_current_account_pct_gdp"], V)
addp("European Commission", "tfp_growth", (tfp.pct_change()*100).round(2).to_dict(), V)
addp("European Commission", "potential_growth", (pot.pct_change()*100).round(2).to_dict(), V)
addp("European Commission", "output_gap", am["AVGDGP"]["data"], V)
addp("European Commission", "nawru", am["ZNAWRU"]["data"], V)

# OECD EO119 (June 2026)
oe = load("oecd_eo119_GRC.json"); V = "OECD EO119 (June 2026)"
addp("OECD", "gdp_growth", oe["GDPV_ANNPCT"], V)
addp("OECD", "hicp_inflation", oe["CPIH_YTYPCT"], V)
addp("OECD", "unemployment_rate", oe["UNR"], V)
addp("OECD", "gg_balance_pct_gdp", oe["NLGQ"], V)
addp("OECD", "current_account_pct_gdp", oe["CBGDPR"], V)
addp("OECD", "output_gap", oe["GAP"], V)
addp("OECD", "gg_gross_financial_liabilities_pct_gdp", oe["GGFLQ"], V)

# Bank of Greece, MinFin (manual)
man = load("official_projections_manual.json")
bog = man["bank_of_greece"]; V = "BoG " + bog["vintage"]
for k, var in [("gdp_growth","gdp_growth"),("hicp_inflation","hicp_inflation"),("unemployment_rate","unemployment_rate"),("public_debt_pct_gdp","public_debt_pct_gdp"),("primary_balance_pct_gdp","primary_balance_pct_gdp"),("current_account_pct_gdp","current_account_pct_gdp"),("gfcf_growth","investment_growth")]:
    addp("Bank of Greece", var, bog[k], V, entry="manual")
mf = man["minfin_apr2026"]; V = "MinFin APR 2026-04"
for k, var in [("gdp_growth","gdp_growth"),("hicp_inflation","hicp_inflation"),("unemployment_rate","unemployment_rate"),("public_debt_pct_gdp","public_debt_pct_gdp"),("primary_balance_pct_gdp","primary_balance_pct_gdp"),("gg_balance_pct_gdp","gg_balance_pct_gdp"),("potential_growth","potential_growth"),("gfcf_growth","investment_growth")]:
    addp("Ministry of Finance", var, mf[k], V, entry="manual")
mt = man["minfin_mtfsp_oct2024"]; V = "MinFin MTFSP 2024-10"
for k, var in [("gdp_growth","gdp_growth"),("unemployment_rate","unemployment_rate"),("public_debt_pct_gdp","public_debt_pct_gdp"),("primary_balance_pct_gdp","primary_balance_pct_gdp"),("gg_balance_pct_gdp","gg_balance_pct_gdp"),("potential_growth","potential_growth")]:
    addp("MinFin MTFSP 2025-28", var, mt[k], V, entry="manual")

# Eurostat EUROPOP2023
ep = load("eurostat_europop2023_assumptions.json"); V = "EUROPOP2023"
addp("Eurostat EUROPOP2023", "old_age_dependency", ep["OLDDEP1_BSL"], V)
addp("Eurostat EUROPOP2023", "fertility_rate", ep["TFR_assumption_BSL"], V)
addp("Eurostat EUROPOP2023", "population_mn", {y: v/1e6 for y, v in e2["proj_23np"]["series"]["PER|TOTAL|T|BSL"].items()}, V)

projdf = pd.DataFrame(proj).sort_values(["variable","institution","year"])

# ---------------- Write ----------------
hist = hist.sort_values(["variable","year"]).drop_duplicates(["variable","year"], keep="first")
hist.to_csv(os.path.join(OUT, "2026-09-03-greece-macro-tidy.csv"), index=False)
wide = hist.pivot_table(index="year", columns="variable", values="value", aggfunc="first").round(4)
wide.to_csv(os.path.join(OUT, "2026-09-03-greece-macro-wide.csv"))
projdf.to_csv(os.path.join(OUT, "2026-09-03-official-projections.csv"), index=False)
print(f"history rows: {len(hist)}, variables: {hist.variable.nunique()}, years {hist.year.min()}-{hist.year.max()}")
print(f"projection rows: {len(projdf)}, institutions: {projdf.institution.nunique()}")
print(wide.loc[2019:2025, ["gdp_growth","hicp_inflation","unemployment_rate","public_debt_pct_gdp","private_debt_pct_gdp","fertility_rate","tfp_growth","tfp_solow_idx_2020"]].to_string())
