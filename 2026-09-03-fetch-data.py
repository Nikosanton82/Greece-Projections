"""
2026-09-03-fetch-data.py
Refresh the raw API snapshots in data/raw/ that 2026-09-03-build-dataset.py consumes.
Sources: Eurostat JSON-stat API, IMF WEO DataMapper, AMECO via DBnomics, OECD SDMX (Economic Outlook).
Bank of Greece / Ministry of Finance projections are PDFs: edit data/raw/official_projections_manual.json by hand.

Requires: requests, pandas.  Run:  python 2026-09-03-fetch-data.py
Note: needs open outbound HTTPS to ec.europa.eu, imf.org, api.db.nomics.world, sdmx.oecd.org.
"""
import os, json, datetime, requests
HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, "data", "raw"); os.makedirs(RAW, exist_ok=True)
TODAY = datetime.date.today().isoformat()
S = requests.Session(); S.headers["User-Agent"] = "greece-projections/1.0"

# ---------------- Eurostat ----------------
ES = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
def es_parse(j):
    ids, size, dims = j["id"], j["size"], j["dimension"]
    cats = [sorted(dims[d]["category"]["index"], key=lambda k: dims[d]["category"]["index"][k]) for d in ids]
    recs = []
    for k, v in j["value"].items():
        idx = int(k); rec = {}
        for d in range(len(ids)-1, -1, -1):
            rec[ids[d]] = cats[d][idx % size[d]]; idx //= size[d]
        rec["value"] = v; recs.append(rec)
    return recs
def es_compact(ds, params):
    r = S.get(ES + ds, params=dict(format="JSON", lang="EN", geo="EL", **params), timeout=60); r.raise_for_status(); j = r.json()
    series = {}
    for rec in es_parse(j):
        key = "|".join(rec[k] for k in rec if k not in ("time", "geo", "freq", "value"))
        series.setdefault(key, {})[rec["time"]] = rec["value"]
    return dict(label=j["label"], updated=j.get("updated"), series=series)
def multi(**kw):  # requests encodes lists as repeated params
    return {k: v for k, v in kw.items()}

batch1 = {
  "nama_10_gdp_lvl": es_compact("nama_10_gdp", multi(na_item=["B1GQ","P51G","P3","P6","P7"], unit=["CP_MEUR","CLV15_MEUR"], sinceTimePeriod=1995)),
  "nama_10_gdp_defl": es_compact("nama_10_gdp", multi(na_item="B1GQ", unit=["PD15_NAC","PD_PCH_PRE_NAC"], sinceTimePeriod=1995)),
  "nama_10_pc": es_compact("nama_10_pc", multi(na_item="B1GQ", unit=["CP_EUR_HAB","CLV15_EUR_HAB","CP_PPS_EU27_2020_HAB"], sinceTimePeriod=1995)),
  "prc_hicp_aind": es_compact("prc_hicp_aind", multi(coicop="CP00", unit="RCH_A_AVG", sinceTimePeriod=1996)),
  "une_rt_a": es_compact("une_rt_a", multi(age="Y15-74", sex="T", unit="PC_ACT", sinceTimePeriod=1995)),
  "gov_10dd_edpt1": es_compact("gov_10dd_edpt1", multi(sector="S13", na_item=["GD","B9"], unit="PC_GDP", sinceTimePeriod=1995)),
  "gov_10a_main": es_compact("gov_10a_main", multi(sector="S13", na_item=["D41PAY","TR","TE"], unit="PC_GDP", sinceTimePeriod=1995)),
}
json.dump(batch1, open(os.path.join(RAW, "eurostat_batch1.json"), "w"))
batch2 = {
  "demo_find": es_compact("demo_find", multi(indic_de="TOTFERRT", sinceTimePeriod=1990)),
  "demo_gind": es_compact("demo_gind", multi(indic_de=["JAN","CNMIGRAT","NATGROW","GROW"], sinceTimePeriod=1995)),
  "demo_pjanind": es_compact("demo_pjanind", multi(indic_de=["OLDDEP1","MEDAGEPOP","PC_Y65_MAX"], sinceTimePeriod=1995)),
  "tipspd20": es_compact("tipspd20", multi(unit="PC_GDP", sinceTimePeriod=1995)),
  "lfsi_emp_a": es_compact("lfsi_emp_a", multi(indic_em="EMP_LFS", unit="PC_POP", age="Y20-64", sex="T", sinceTimePeriod=1995)),
  "lfsa_argan": es_compact("lfsa_argan", multi(age="Y15-64", sex="T", citizen="TOTAL", unit="PC", sinceTimePeriod=1995)),
  "nama_10_a10_e": es_compact("nama_10_a10_e", multi(nace_r2="TOTAL", na_item="EMP_DC", unit=["THS_PER","THS_HW"], sinceTimePeriod=1995)),
  "nama_10_lp_ulc": es_compact("nama_10_lp_ulc", multi(na_item=["NULC_PER","RLPR_PER","RLPR_HW"], unit=["PCH_PRE","I15"], sinceTimePeriod=1995)),
  "ert_eff_ic_a": es_compact("ert_eff_ic_a", multi(unit="I15", exch_rt=["REER_IC42_CPI","REER_EA20_ULCT"], sinceTimePeriod=1995)),
  "proj_23np": es_compact("proj_23np", multi(projection="BSL", sex="T", age="TOTAL", unit="PER", sinceTimePeriod=2022, untilTimePeriod=2040)),
}
json.dump(batch2, open(os.path.join(RAW, "eurostat_batch2.json"), "w"))
niip = es_compact("tipsii40", multi(sinceTimePeriod=2003))
niip_q4 = {k[:4]: v for k, v in list(niip["series"].values())[0].items() if k.endswith("Q4")}
batch3 = {
  "tipspd22": es_compact("tipspd22", multi(unit="PC_GDP", sinceTimePeriod=1995)),
  "irt_lt_mcby_a": es_compact("irt_lt_mcby_a", multi(sinceTimePeriod=1995)),
  "tipsii40_niip_q4": dict(label="NIIP % GDP (Q4)", updated=niip["updated"], series={"NIIP_PC_GDP": niip_q4}),
  "nasa_10_ki": es_compact("nasa_10_ki", multi(na_item="SRG_S14_S15", unit="PC", sinceTimePeriod=1995)),
}
json.dump(batch3, open(os.path.join(RAW, "eurostat_batch3.json"), "w"))
# EUROPOP2023 assumptions: dependency ratio and TFR (sum of assumed age-specific rates)
dep = es_compact("proj_23ndbi", multi(projection="BSL", indic_de="OLDDEP1", sinceTimePeriod=2025, untilTimePeriod=2040))
r = S.get(ES + "proj_23naasfr", params=dict(format="JSON", lang="EN", geo="EL", projection="BSL", sinceTimePeriod=2025, untilTimePeriod=2040), timeout=60).json()
tfr = {}
for rec in es_parse(r):
    if rec["age"] not in ("TOTAL",): tfr[rec["time"]] = tfr.get(rec["time"], 0) + rec["value"]
json.dump(dict(source="Eurostat EUROPOP2023 (proj_23ndbi, proj_23naasfr)", retrieved=TODAY, OLDDEP1_BSL=list(dep["series"].values())[0],
               TFR_assumption_BSL={k: round(v, 3) for k, v in tfr.items()}), open(os.path.join(RAW, "eurostat_europop2023_assumptions.json"), "w"))

# ---------------- IMF WEO ----------------
IMF = "https://www.imf.org/external/datamapper/api/v1/"
inds = ["NGDP_RPCH","NGDPD","NGDPDPC","PPPPC","PPPGDP","PCPIPCH","PCPIEPCH","LUR","LP","BCA_NGDPD","GGXWDG_NGDP","GGXCNL_NGDP"]
meta = S.get(IMF + "indicators", timeout=60).json()["indicators"]
imf = dict(vintage=meta["NGDP_RPCH"]["source"], retrieved=TODAY, source_url=IMF + "{indicator}/GRC")
for i in inds:
    imf[i] = S.get(IMF + f"{i}/GRC", timeout=60).json()["values"][i]["GRC"]
json.dump(imf, open(os.path.join(RAW, "imf_weo_apr2026_GRC.json"), "w"))

# ---------------- AMECO via DBnomics ----------------
DB = "https://api.db.nomics.world/v22/series/AMECO/"
def ameco(code, pick=None):
    j = S.get(DB + code, params=dict(observations=1, limit=200), timeout=60).json()
    docs = [d for d in j["series"]["docs"] if d["series_code"].startswith("GRC.")]
    d = next((x for x in docs if pick is None or pick in x["series_code"]), docs[0])
    return dict(name=d["series_name"], data={p: v for p, v in zip(d["period"], d["value"]) if int(p) >= 1995 and v != "NA"})
am = dict(source="AMECO via DBnomics", retrieved=TODAY)
for c in ["ZVGDF","OVGDP","AVGDGP","ZNAWRU","OKND"]: am[c] = ameco(c)
json.dump(am, open(os.path.join(RAW, "ameco_dbnomics_GRC.json"), "w"))
ec = dict(source="EC forecast as embedded in AMECO (via DBnomics)", retrieved=TODAY)
for key, code, pick in [("OVGD_real_gdp_bn2020","OVGD",None),("ZCPIH_hicp_index_2015","ZCPIH",None),("ZUTN_unemployment_rate","ZUTN",None),
                        ("UDGG_debt_pct_gdp","UDGG",".319."),("UBLG_balance_pct_gdp","UBLG",".319."),("UBLGI_primary_balance_pct_gdp","UBLGI",".319."),
                        ("UBCA_current_account_pct_gdp","UBCA",".310."),("UIGT_gfcf_bn_eur","UIGT","1.0.0.0"),("NLTN_labour_force_thousands","NLTN",None)]:
    ec[key] = {p: v for p, v in ameco(code, pick)["data"].items() if int(p) >= 2019}
json.dump(ec, open(os.path.join(RAW, "ec_spring2026_forecast_GRC.json"), "w"))

# ---------------- OECD Economic Outlook ----------------
url = "https://sdmx.oecd.org/public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO,/GRC.GDPV_ANNPCT+CPIH_YTYPCT+UNR+GGFLQ+NLGQ+CBGDPR+GAP.A"
j = S.get(url, params=dict(startPeriod=2019, format="jsondata"), timeout=90).json()
ds = j["data"]["dataSets"][0]; st = j["data"]["structures"][0] if "structures" in j["data"] else j["data"]["structure"]
sd = st["dimensions"]["series"]; od = st["dimensions"]["observation"][0]["values"]
oe = dict(source=st.get("name", "OECD Economic Outlook"), retrieved=TODAY)
for k, s in ds["series"].items():
    idx = [int(x) for x in k.split(":")]; meas = sd[1]["values"][idx[1]]["id"]
    oe[meas] = {od[int(oi)]["id"]: v[0] for oi, v in s["observations"].items()}
json.dump(oe, open(os.path.join(RAW, "oecd_eo119_GRC.json"), "w"))
print("raw snapshots refreshed in", RAW)
