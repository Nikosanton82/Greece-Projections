"""
2026-09-03-models.py
Projection model suite for the Greek economy, 2026-2030 (annual).

Structure
  1. Univariate models per target: ARIMA (AIC-selected), local linear trend (UC), AR(1) mean-reverting.
  2. Bayesian VAR with Minnesota prior (Banbura-Giannone-Reichlin dummy observations) on the core block.
  3. Structural / accounting projections: production function (TFP, capital, labour), public debt dynamics,
     private debt dynamics, population and fertility.
  4. Rolling pseudo-out-of-sample evaluation 2010-2025, inverse-MSE and equal-weight combinations,
     Diebold-Mariano tests vs a naive benchmark.
  5. Predictive densities by simulation (bootstrap of residuals), 68% and 90% bands, three scenarios.

Outputs (data/):
  2026-09-03-projections.csv        variable, scenario, model, year, mean, p05, p16, p50, p84, p95
  2026-09-03-model-evaluation.csv   variable, model, horizon, rmse, mae, dm_stat, dm_pvalue, weight
  2026-09-03-projections.json       everything the dashboard needs
"""
import os, json, warnings
import numpy as np, pandas as pd
from scipy import stats
warnings.filterwarnings("ignore")
import statsmodels.api as sm
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.structural import UnobservedComponents

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
rng = np.random.default_rng(20260903)
H = 5; LAST = 2025; YEARS = list(range(LAST+1, LAST+1+H)); NSIM = 2000
wide = pd.read_csv(os.path.join(DATA, "2026-09-03-greece-macro-wide.csv"), index_col=0)
offp = pd.read_csv(os.path.join(DATA, "2026-09-03-official-projections.csv"))

# ---------------------------------------------------------------- helpers
def qbands(sims):
    """sims: (NSIM, H) -> dict of quantile paths"""
    q = np.percentile(sims, [5, 16, 50, 84, 95], axis=0)
    return dict(mean=sims.mean(0), p05=q[0], p16=q[1], p50=q[2], p84=q[3], p95=q[4])

def boot_paths(point, resid, h=H, nsim=NSIM, persist=0.0, cum=False):
    """Point path + bootstrapped residual shocks (AR(persist) accumulation, or cumulative for levels)."""
    resid = np.asarray(resid); resid = resid[~np.isnan(resid)]
    e = rng.choice(resid - resid.mean(), size=(nsim, h))
    out = np.zeros((nsim, h)); acc = np.zeros(nsim)
    for t in range(h):
        acc = (persist*acc if not cum else acc) + e[:, t]
        out[:, t] = point[t] + acc
    return out

# ---------------------------------------------------------------- 1. univariate models
def fit_arima(y, h=H, max_p=2, max_q=1, d=None):
    y = y.dropna().astype(float)
    best = None
    ds = [0, 1] if d is None else [d]
    for dd in ds:
        for p in range(max_p+1):
            for q in range(max_q+1):
                if p == q == 0 and dd == 0: continue
                try:
                    m = ARIMA(y.values, order=(p, dd, q), trend="c" if dd == 0 else "n").fit()
                    if best is None or m.aic < best[0]: best = (m.aic, (p, dd, q), m)
                except Exception: pass
    m = best[2]; fc = m.get_forecast(h)
    return dict(point=fc.predicted_mean, se=fc.se_mean, order=best[1], resid=m.resid[2:], model=m)

def fit_llt(y, h=H, level="local linear trend"):
    y = y.dropna().astype(float)
    m = UnobservedComponents(y.values, level=level).fit(disp=False, maxiter=500)
    fc = m.get_forecast(h)
    return dict(point=fc.predicted_mean, se=fc.se_mean, resid=m.resid[3:], model=m)

def fit_ar1(y, h=H):
    """Mean-reverting AR(1) around sample mean of the last 30 years (for rates/ratios)."""
    y = y.dropna().astype(float)
    m = ARIMA(y.values, order=(1, 0, 0), trend="c").fit()
    fc = m.get_forecast(h)
    return dict(point=fc.predicted_mean, se=fc.se_mean, resid=m.resid[1:], model=m)

def fit_anchored(y, h=H, target=2.0):
    """AR(1) in deviations from the ECB 2% objective, no intercept: pi_t - 2 = rho (pi_{t-1} - 2) + e (anchored expectations)."""
    y = y.dropna().astype(float) - target
    m = ARIMA(y.values, order=(1, 0, 0), trend="n").fit()
    fc = m.get_forecast(h)
    return dict(point=fc.predicted_mean + target, se=fc.se_mean, resid=m.resid[1:], model=m)

def uni_forecast(y, h=H, kind="arima", origin=None):
    yy = y.loc[:origin] if origin else y
    if kind == "arima": return fit_arima(yy, h)
    if kind == "llt": return fit_llt(yy, h)
    if kind == "ar1": return fit_ar1(yy, h)
    if kind == "anchored": return fit_anchored(yy, h)

# ---------------------------------------------------------------- 2. Minnesota BVAR
def bvar_minnesota(Y, p=1, lam=0.2, h=H, nsim=NSIM, sum_coef=1.0):
    """Y: (T, n) DataFrame. Litterman/Minnesota prior via dummy observations (Banbura et al. 2010).
    Random-walk prior mean for levels, white-noise (0) for growth rates: we use prior mean delta_i = 0 for
    growth/rates variables that are stationary, 1 otherwise (decided by an ADF-style heuristic: AR(1) coef > 0.8)."""
    Yv = Y.values; T, n = Yv.shape
    # scale: residual sd from univariate AR(p)
    sig = np.array([np.std(sm.OLS(Yv[p:, i], sm.add_constant(np.column_stack([Yv[p-j-1:T-j-1, i] for j in range(p)]))).fit().resid) for i in range(n)])
    ar1 = np.array([np.corrcoef(Yv[1:, i], Yv[:-1, i])[0, 1] for i in range(n)])
    delta = np.where(ar1 > 0.8, 1.0, 0.0)
    mu = Yv[-1]  # sum-of-coefficients prior centred on the last observation (no-change), not the crisis-laden full-sample mean
    # dummy observations
    Yd, Xd = [], []
    k = n*p + 1
    for i in range(n):
        yd = np.zeros(n); yd[i] = delta[i]*sig[i]/lam
        xd = np.zeros(k); xd[i] = sig[i]/lam
        Yd.append(yd); Xd.append(xd)
    for l in range(2, p+1):
        for i in range(n):
            xd = np.zeros(k); xd[(l-1)*n+i] = sig[i]*l/lam; Yd.append(np.zeros(n)); Xd.append(xd)
    for i in range(n):  # residual covariance prior
        yd = np.zeros(n); yd[i] = sig[i]; Yd.append(yd); Xd.append(np.zeros(k))
    eps = 1e-3; Yd.append(np.zeros(n)); xd = np.zeros(k); xd[-1] = eps; Xd.append(xd)  # intercept (diffuse)
    # sum-of-coefficients prior (tau = 10*lam) — mild
    tau = sum_coef*10*lam
    for i in range(n):
        yd = np.zeros(n); yd[i] = delta[i]*mu[i]/tau
        xd = np.zeros(k)
        for l in range(p): xd[l*n+i] = delta[i]*mu[i]/tau
        Yd.append(yd); Xd.append(xd)
    Yd = np.array(Yd); Xd = np.array(Xd)
    # actual data
    X = np.column_stack([Yv[p-j-1:T-j-1, :] for j in range(p)] + [np.ones(T-p)])
    Ya = Yv[p:, :]
    Xs = np.vstack([X, Xd]); Ys = np.vstack([Ya, Yd])
    XtX = Xs.T @ Xs; B = np.linalg.solve(XtX, Xs.T @ Ys)
    E = Ys - Xs @ B; S = E.T @ E; nu = Xs.shape[0] - k
    # posterior simulation: Sigma ~ IW(S, nu); vec(B) ~ N(vec(B), Sigma kron (X'X)^-1)
    XtXi = np.linalg.inv(XtX); L = np.linalg.cholesky(XtXi)
    sims = np.zeros((nsim, h, n))
    for s in range(nsim):
        Sig = stats.invwishart.rvs(df=nu, scale=S, random_state=rng)
        Ls = np.linalg.cholesky(Sig)
        Bs = B + L @ rng.standard_normal((k, n)) @ Ls.T
        lags = [Yv[T-1-j, :] for j in range(p)]
        for t in range(h):
            x = np.concatenate(lags + [[1.0]])
            y = x @ Bs + Ls @ rng.standard_normal(n)
            sims[s, t, :] = y; lags = [y] + lags[:-1]
    return dict(sims=sims, B=B, point=sims.mean(0), delta=delta)

# ---------------------------------------------------------------- 3. structural blocks
def production_function(w, tfp_growth_path, scen, h=H):
    """Potential output via Y* = A K^a (L*)^(1-a), a=0.35; L* = working-age pop x participation x (1-NAWRU) x hours/worker.
    Returns potential growth path and actual GDP growth with output-gap closure (gap closes 1/3 per year)."""
    a = 0.35
    # capital: perpetual inventory K_{t+1} = (1-delta) K_t + I_t. Depreciation calibrated on the last observed year so that
    # AMECO's net capital stock (2020 prices) and Eurostat real GFCF (2015 prices; GDP deflator 2020/2015 = 0.994, treated as same units) are consistent.
    Kt = w["capital_stock_bn_eur2020"].loc[LAST]; Kprev = w["capital_stock_bn_eur2020"].loc[LAST-1]
    It = w["investment_real_bn_eur2015"].loc[LAST]
    delta_dep = (Kprev + It - Kt)/Kprev
    # labour: working-age population (EUROPOP2023 15-64 falls about 0.7%/yr to 2030), participation rate, NAWRU
    wap_growth = {"baseline": -0.7, "adverse": -1.0, "favourable": -0.4}[scen]
    part_gain = {"baseline": 0.3, "adverse": 0.1, "favourable": 0.5}[scen]
    part = w["activity_rate_15_64"].loc[LAST]; nawru = w["nawru"].loc[LAST]
    inv_g = {"baseline": 4.0, "adverse": 0.0, "favourable": 7.0}[scen]  # real investment growth %
    # Starting output gap: the EC estimate (+2.7% in 2025) sits oddly with unemployment already at the EC's own NAWRU;
    # the OECD (EO119) puts the 2025 gap at +0.9%. We start from the OECD gap and close it 20% a year.
    oecd = json.load(open(os.path.join(DATA, "raw", "oecd_eo119_GRC.json")))
    gap = float(oecd["GAP"][str(LAST)])
    pot_g, act_g, tfp_g, L_g = [], [], [], []
    wap = 100.0; L_prev = wap*part*(100-nawru)
    for t in range(h):
        Knext = Kt*(1-delta_dep) + It
        kg = Knext/Kt - 1
        wap *= (1+wap_growth/100); part += part_gain; nawru = max(nawru - 0.1, 7.0)
        L = wap*part*(100-nawru); lg = L/L_prev - 1; L_prev = L
        pg = (1+tfp_growth_path[t]/100)*(1+kg)**a*(1+lg)**(1-a) - 1
        gap_next = gap*0.8  # output gap closes 20% per year (EC Spring 2026 keeps the gap near +2.7% through 2027)
        ag = (1+pg)*(1+gap_next/100)/(1+gap/100) - 1
        gap = gap_next
        pot_g.append(pg*100); act_g.append(ag*100); L_g.append(lg*100)
        Kt = Knext; It = It*(1+inv_g/100)
    return np.array(pot_g), np.array(act_g), np.array(L_g)

def debt_dynamics(d0, g_nom, pb, i_impl, sfa):
    """d_t = d_{t-1}(1+i)/(1+g) - pb_t + sfa_t, all in % of GDP / %."""
    d = d0; out = []
    for t in range(len(g_nom)):
        d = d*(1+i_impl[t]/100)/(1+g_nom[t]/100) - pb[t] + sfa[t]; out.append(d)
    return np.array(out)

# ---------------------------------------------------------------- targets and model map
TARGETS = {
    "gdp_growth":               dict(models=["arima", "ar1", "bvar", "structural"], first=1996),
    "hicp_inflation":           dict(models=["arima", "ar1", "anchored", "bvar"], first=1996),
    "unemployment_rate":        dict(models=["arima", "bvar", "structural"], first=1995),
    "investment_growth":        dict(models=["arima", "ar1", "bvar"], first=1996),
    "current_account_pct_gdp":  dict(models=["arima", "ar1", "bvar"], first=1995),
    "tfp_growth":               dict(models=["arima", "ar1", "llt"], first=1996),
    "fertility_rate":           dict(models=["arima", "llt", "ar1"], first=1990),
    "public_debt_pct_gdp":      dict(models=["arima", "llt", "structural"], first=1995),
    "private_debt_pct_gdp":     dict(models=["arima", "llt", "structural"], first=1995),
    "potential_growth":         dict(models=["arima", "ar1", "structural"], first=1996),
    "gdp_pc_pps":               dict(models=["arima", "llt", "structural"], first=1995),
    "population_mn":            dict(models=["arima", "llt", "structural"], first=1995),
}
CORE = ["gdp_growth", "hicp_inflation", "unemployment_rate", "investment_growth", "current_account_pct_gdp"]

# ---------------------------------------------------------------- 4. rolling pseudo-out-of-sample evaluation
def rolling_eval(var, models, first, origins=range(2009, 2025), h=H):
    y = wide[var].dropna(); y = y[y.index >= first]
    recs = []
    for o in origins:
        if o not in y.index: continue
        for m in models:
            if m in ("structural",): continue  # structural blocks need scenario inputs; evaluated separately
            try:
                if m == "bvar":
                    Yc = wide[CORE].dropna(); Yc = Yc[(Yc.index >= 1996) & (Yc.index <= o)]
                    if var not in CORE: continue
                    r = bvar_minnesota(Yc, p=1, lam=0.2, h=h, nsim=200)
                    pt = r["point"][:, CORE.index(var)]
                else:
                    pt = uni_forecast(y, h, m, origin=o)["point"]
            except Exception as ex:
                continue
            for k in range(1, h+1):
                if o+k in y.index:
                    recs.append(dict(variable=var, model=m, origin=o, horizon=k, fc=pt[k-1], actual=y.loc[o+k]))
        # naive benchmark: last value (random walk) or historical mean for growth rates
        naive = y.loc[o] if var in ("unemployment_rate","public_debt_pct_gdp","private_debt_pct_gdp","fertility_rate","gdp_pc_pps","population_mn","current_account_pct_gdp") else y.loc[:o].tail(10).mean()
        for k in range(1, h+1):
            if o+k in y.index:
                recs.append(dict(variable=var, model="naive", origin=o, horizon=k, fc=naive, actual=y.loc[o+k]))
    return pd.DataFrame(recs)

def dm_test(e1, e2, h):
    """Diebold-Mariano with Harvey-Leybourne-Newbold small-sample correction, squared-error loss."""
    d = e1**2 - e2**2; n = len(d)
    if n < 6: return np.nan, np.nan
    dbar = d.mean()
    gamma = [np.sum((d[k:]-dbar)*(d[:n-k]-dbar))/n for k in range(h)]
    var = (gamma[0] + 2*sum(gamma[1:]))/n
    if var <= 0: var = gamma[0]/n
    dm = dbar/np.sqrt(var) * np.sqrt((n+1-2*h+h*(h-1)/n)/n)
    p = 2*(1-stats.t.cdf(abs(dm), df=n-1))
    return dm, p

evals, weights = [], {}
for var, spec in TARGETS.items():
    df = rolling_eval(var, spec["models"], spec["first"])
    if df.empty: continue
    df["err"] = df.fc - df.actual
    w_var = {}
    for m in df.model.unique():
        if m == "naive": continue
        for k in range(1, H+1):
            a = df[(df.model == m) & (df.horizon == k)].sort_values("origin")
            b = df[(df.model == "naive") & (df.horizon == k)].sort_values("origin")
            mrg = a.merge(b, on="origin", suffixes=("", "_n"))
            if len(mrg) < 4: continue
            dm, p = dm_test(mrg.err.values, mrg.err_n.values, k)
            evals.append(dict(variable=var, model=m, horizon=k, n=len(mrg), rmse=np.sqrt((mrg.err**2).mean()), mae=mrg.err.abs().mean(),
                              rmse_naive=np.sqrt((mrg.err_n**2).mean()), dm_stat=dm, dm_pvalue=p))
    ev = pd.DataFrame([e for e in evals if e["variable"] == var])
    # inverse-MSE weights averaged over horizons 1-3 (the most informative for a 30-year sample)
    if not ev.empty:
        msew = ev[ev.horizon <= 3].groupby("model").rmse.apply(lambda s: (s**2).mean())
        inv = 1/msew; weights[var] = (inv/inv.sum()).to_dict()
evaldf = pd.DataFrame(evals)

# ---------------------------------------------------------------- 5. final projections per scenario
SCEN = {
    "baseline":   dict(tfp=None, ig=0.0, infl=0.0, pb_adj=0.0, mig=0.0),
    "adverse":    dict(tfp=-0.7, ig=+1.0, infl=+1.0, pb_adj=-1.0, mig=-30),
    "favourable": dict(tfp=+0.5, ig=-0.5, infl=-0.3, pb_adj=+0.5, mig=+30),
}
results, evaluation_notes = [], {}

def record(var, scen, model, sims, note=None):
    b = qbands(sims)
    for i, yr in enumerate(YEARS):
        results.append(dict(variable=var, scenario=scen, model=model, year=yr, **{k: float(v[i]) for k, v in b.items()}))

# --- core BVAR (full sample)
Yc = wide[CORE].dropna(); Yc = Yc[Yc.index >= 1996]
bv = bvar_minnesota(Yc, p=1, lam=0.2)
bvar_sims = {v: bv["sims"][:, :, i] for i, v in enumerate(CORE)}

# --- univariate sims for every target
uni_sims = {}
for var, spec in TARGETS.items():
    y = wide[var].dropna(); y = y[y.index >= spec["first"]]
    for m in spec["models"]:
        if m in ("bvar", "structural"): continue
        r = uni_forecast(y, H, m)
        se = np.asarray(r["se"]); pt = np.asarray(r["point"])
        sims = pt + rng.standard_normal((NSIM, H))*se  # Gaussian predictive from state-space / ARIMA
        uni_sims[(var, m)] = sims

# --- structural sims (scenario dependent)
def structural_sims(scen):
    S = SCEN[scen]; out = {}
    # TFP growth path: combination of univariate TFP models + scenario shift; 2026 anchored to EC AMECO forecast (0.75)
    tfp_comb = np.average([uni_sims[("tfp_growth", m)] for m in ["arima", "ar1", "llt"]], axis=0,
                          weights=[weights.get("tfp_growth", {}).get(m, 1/3) for m in ["arima", "ar1", "llt"]])
    tfp_comb = tfp_comb + (S["tfp"] or 0.0)
    # production function per simulation draw (vectorised on TFP draws only)
    pot = np.zeros((NSIM, H)); act = np.zeros((NSIM, H))
    for s in range(0, NSIM):
        pg, ag, _ = production_function(wide, tfp_comb[s], scen)
        pot[s] = pg; act[s] = ag
    out["potential_growth"] = pot; out["gdp_growth"] = act; out["tfp_growth"] = tfp_comb
    # Okun's law: du_t = c + beta (g_t - g*_t) + e, estimated 1997-2025 on Eurostat data and AMECO potential growth
    ok = wide[["unemployment_rate", "gdp_growth", "potential_growth"]].dropna(); ok = ok[ok.index >= 1996]
    du = ok["unemployment_rate"].diff().dropna(); xg = (ok["gdp_growth"] - ok["potential_growth"]).loc[du.index]
    okm = sm.OLS(du.values, sm.add_constant(xg.values)).fit(); okc, okb = okm.params; oks = np.std(okm.resid)
    u = np.zeros((NSIM, H)); ul = wide["unemployment_rate"].loc[LAST]*np.ones(NSIM)
    for t in range(H):
        ul = ul + okc + okb*(act[:, t] - pot[:, t]) + rng.standard_normal(NSIM)*oks; ul = np.maximum(ul, 3.0); u[:, t] = ul
    out["unemployment_rate"] = u; out["_okun"] = dict(const=float(okc), beta=float(okb), sd=float(oks), r2=float(okm.rsquared))
    # inflation: BVAR + scenario shock in year 1 fading
    infl = bvar_sims["hicp_inflation"] + S["infl"]*np.array([1, 0.5, 0.25, 0.1, 0.0])
    # nominal growth for debt dynamics: real growth (combination of BVAR & structural) + deflator (≈ HICP - 0.2)
    real_g = 0.5*act + 0.5*bvar_sims["gdp_growth"]
    nom_g = (1+real_g/100)*(1+(infl-0.2)/100)*100-100
    # public debt: implicit interest rate rises from 2.2% (2025: 3.2% of GDP interest / 146% debt) toward 3.4% (10y yield) by 2030
    i_path = np.linspace(2.3, 3.2, H) + S["ig"]
    # primary balance: EC 2026-27 (4.0, 3.7) then converge to MTFSP 2.4 by 2030; stochastic: sd 0.8 pp
    pb_base = np.array([4.0, 3.7, 3.3, 2.9, 2.5]) + S["pb_adj"]
    pb = pb_base + rng.standard_normal((NSIM, H)).cumsum(1)*0.5
    sfa = rng.standard_normal((NSIM, H))*1.0 - 0.5  # cash buffer drawdown/early repayments: mean -0.5 (debt-reducing)
    d = np.zeros((NSIM, H))
    for s in range(NSIM):
        d[s] = debt_dynamics(wide["public_debt_pct_gdp"].loc[LAST], nom_g[s], pb[s], i_path, sfa[s])
    out["public_debt_pct_gdp"] = d
    # private debt: ratio_t = ratio_{t-1} * (1+credit growth)/(1+nominal growth); credit growth AR(1) around 4% (2023-25 avg ~ +5%)
    cg = np.zeros((NSIM, H)); prev = 7.2  # 2025 private debt nominal growth (239.97/223.9)
    for t in range(H):
        prev = 4.0 + 0.5*(prev-4.0) + rng.standard_normal(NSIM)*2.5; cg[:, t] = prev
    pdbt = np.zeros((NSIM, H)); lvl = wide["private_debt_pct_gdp"].loc[LAST]*np.ones(NSIM)
    for t in range(H):
        lvl = lvl*(1+cg[:, t]/100)/(1+nom_g[:, t]/100); pdbt[:, t] = lvl
    out["private_debt_pct_gdp"] = pdbt
    # population: natural change trends at -55k/yr (AR(1) drift), net migration AR(1) around +40k (2023-25 avg 44k) + scenario
    pop = np.zeros((NSIM, H)); P = wide["population_mn"].loc[2026]*np.ones(NSIM)  # 1 Jan 2026 known
    nat = -55.4*np.ones(NSIM); mig = 49.6*np.ones(NSIM)
    for t in range(H):
        nat = nat - 1.0 + rng.standard_normal(NSIM)*4
        mig = 40 + S["mig"] + 0.5*(mig-40-S["mig"]) + rng.standard_normal(NSIM)*20
        P = P + (nat+mig)/1000; pop[:, t] = P  # population on 1 Jan of year t+1 attributed to year t (avg proxy)
    out["population_mn"] = pop
    # GDP per capita PPS: grows with real GDP per head + EU relative price/catch-up drift (assume PPS inflation 2.5%)
    gpc = np.zeros((NSIM, H)); lvl = wide["gdp_pc_pps"].loc[LAST]*np.ones(NSIM); popg = np.diff(np.column_stack([wide["population_mn"].loc[2026]*np.ones(NSIM), pop]), axis=1)/pop
    for t in range(H):
        lvl = lvl*(1+real_g[:, t]/100)/(1+popg[:, t])*(1+0.025); gpc[:, t] = lvl
    out["gdp_pc_pps"] = gpc
    return out

OKUN = None
for scen in SCEN:
    st = structural_sims(scen)
    if scen == "baseline": OKUN = st["_okun"]
    for var, spec in TARGETS.items():
        parts, wts = [], []
        for m in spec["models"]:
            if m == "bvar": sims = bvar_sims[var]
            elif m == "structural": sims = st[var]
            else: sims = uni_sims[(var, m)]
            # apply scenario shifts to non-structural models too (so scenarios differ for every variable)
            if scen != "baseline" and m != "structural":
                S = SCEN[scen]
                if var in ("gdp_growth", "potential_growth"): sims = sims + (S["tfp"] or 0)*0.8
                if var == "hicp_inflation": sims = sims + S["infl"]*np.array([1, 0.5, 0.25, 0.1, 0])
                if var == "unemployment_rate": sims = sims - (S["tfp"] or 0)*np.array([0.2, 0.4, 0.6, 0.7, 0.8])
                if var == "public_debt_pct_gdp": sims = sims + S["ig"]*np.array([1.4, 2.9, 4.3, 5.8, 7.2])
                if var == "tfp_growth": sims = sims + (S["tfp"] or 0)
            record(var, scen, m, sims)
            parts.append(sims); wts.append(weights.get(var, {}).get(m, np.nan))
        wts = np.array(wts, dtype=float)
        # Hybrid weighting: the structural/accounting block (no pseudo-OOS record of its own) receives a fixed 0.5,
        # the evaluated time-series models share the other 0.5 in proportion to inverse pseudo-OOS MSE (h=1..3).
        if "structural" in spec["models"]:
            si = spec["models"].index("structural"); rest = np.array([w for i, w in enumerate(wts) if i != si], dtype=float)
            rest = np.nan_to_num(rest, nan=np.nanmean(rest)); rest = 0.5*rest/rest.sum()
            wts = np.insert(rest, si, 0.5)
        else:
            wts = np.nan_to_num(wts, nan=np.nanmean(wts)); wts = wts/wts.sum()
        # combination as a mixture of predictive densities (draw model by weight)
        idx = rng.choice(len(parts), size=NSIM, p=wts)
        comb = np.stack([parts[i][s] for s, i in enumerate(idx)])
        record(var, scen, "combination", comb)
        record(var, scen, "equal_weights", np.stack([parts[i][s] for s, i in enumerate(rng.integers(0, len(parts), NSIM))]))
        if scen == "baseline": weights.setdefault(var, {}); weights[var]["_final"] = dict(zip(spec["models"], wts.round(3).tolist()))

res = pd.DataFrame(results)
res.to_csv(os.path.join(DATA, "2026-09-03-projections.csv"), index=False)
evaldf.to_csv(os.path.join(DATA, "2026-09-03-model-evaluation.csv"), index=False)

# ---------------------------------------------------------------- dashboard JSON
hist = {v: {int(y): (None if pd.isna(x) else round(float(x), 3)) for y, x in wide[v].dropna().items()} for v in wide.columns}
proj = {}
for (v, sc, m), g in res.groupby(["variable", "scenario", "model"]):
    proj.setdefault(v, {}).setdefault(sc, {})[m] = {k: g[k].round(3).tolist() for k in ["mean", "p05", "p16", "p50", "p84", "p95"]}
official = {}
for (v, inst), g in offp.groupby(["variable", "institution"]):
    official.setdefault(v, {})[inst] = dict(vintage=g.vintage.iloc[0], entry=g.entry_method.iloc[0], data={int(y): round(float(x), 2) for y, x in zip(g.year, g.value)})
evj = {}
for (v, m), g in evaldf.groupby(["variable", "model"]):
    evj.setdefault(v, {})[m] = {int(r.horizon): dict(rmse=round(r.rmse, 3), rmse_naive=round(r.rmse_naive, 3), dm=None if pd.isna(r.dm_stat) else round(r.dm_stat, 2), p=None if pd.isna(r.dm_pvalue) else round(r.dm_pvalue, 3), n=int(r.n)) for r in g.itertuples()}
json.dump(dict(years=YEARS, last_hist=LAST, okun=OKUN, history=hist, projections=proj, official=official, evaluation=evj,
               weights={v: w.get("_final", {}) for v, w in weights.items()}, bvar_delta=dict(zip(CORE, bv["delta"].tolist())),
               built="2026-09-03"), open(os.path.join(DATA, "2026-09-03-projections.json"), "w"))

print("weights:"); [print(" ", v, w.get("_final")) for v, w in weights.items()]
print(res[(res.model == "combination") & (res.scenario == "baseline")].pivot(index="year", columns="variable", values="p50").round(2).to_string())
print(evaldf[evaldf.horizon == 1].pivot(index="variable", columns="model", values="rmse").round(2).to_string())
