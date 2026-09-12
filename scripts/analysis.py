"""
analysis.py  (scripts/)
-----------------------
Från körningar till manuskript i ett kommando.

Vägen dit har varit en serie skript i rätt ordning -- export_tables,
validate_mobility, convergence, check_invariants, figures,
compare_municipalities -- och det är där fel smyger in. Detta kör dem i
ordning, grupperar körningar per scenario, redovisar spridning över frön och
skriver en sammanfattning.

    python scripts/analysis.py --all                  # allt under output/
    python scripts/analysis.py output/run_A output/run_B
    python scripts/analysis.py --all --since 47da14ab # en kodversion
    python scripts/analysis.py --all --no-figures

Skriver till analysis/:
    runs.csv          en rad per körning, med härkomst
    by_scenario.csv   median och spridning per scenario
    report.md         sammanfattning med jämförelse mot referensvärden
    figures/          figurer med data och manifest
"""
import argparse
import datetime
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.analysis.eventlog import collect_runs, group_stats, export

REF = {"median_u_R": 0.70, "u_pct": 7.5, "v_pct": 2.0}


def runs_under(outdir):
    return sorted(os.path.join(outdir, d) for d in os.listdir(outdir)
                  if d != "arkiv" and os.path.isdir(os.path.join(outdir, d))
                  and os.path.isfile(os.path.join(outdir, d, "eventlog.csv")))


def _fmt(v, nd=2):
    return "—" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{nd}f}"


def write_report(df, grouped, out, run_dirs, figdir=None, by='scenario'):
    lines = []
    A = lines.append
    A("# Analys av WORM-körningar\n")
    A(f"Genererad {datetime.datetime.now().isoformat(timespec='seconds')} "
      f"ur {len(df)} körningar.\n")

    # Härkomst först: en jämförelse över blandade kodversioner mäter kodhistorik
    if "commit" in df.columns:
        commits = sorted(df["commit"].dropna().unique())
        A("## Härkomst\n")
        if len(commits) > 1:
            A(f"**Varning:** körningarna kommer från {len(commits)} kodversioner "
              f"({', '.join(commits)}). En jämförelse mellan dem mäter kodhistorik "
              f"snarare än skillnader mellan scenarier. Använd `--since`.\n")
        elif commits:
            A(f"Samtliga körningar är gjorda på commit `{commits[0]}`.\n")
        if df.get("dirty", pd.Series(dtype=bool)).any():
            A(f"**Varning:** {int(df['dirty'].sum())} körning(ar) gjordes med "
              f"ocommittade ändringar och går inte att återskapa.\n")
        if "seed" in df.columns:
            per = df.groupby("scenario")["seed"].nunique() if "scenario" in df else None
            if per is not None:
                A("Frön per scenario: "
                  + ", ".join(f"{k}: {v}" for k, v in per.items()) + "\n")

    # Bokföringen: en modell vars aggregat inte stämmer går inte att dra slutsatser ur
    A("## Bokföring\n")
    if "identity_residual_max" in df.columns:
        bad = df[df["identity_residual_max"].abs() > 0.5]
        if bad.empty:
            A("Identiteten $U = L - J + V$ håller exakt i samtliga körningar.\n")
        else:
            A(f"**Varning:** {len(bad)} körning(ar) bryter identiteten "
              f"$U = L - J + V$ (störst avvikelse "
              f"{bad['identity_residual_max'].abs().max():.0f}). Kör "
              f"`scripts/check_invariants.py` på dem.\n")

    A("## Utfall per scenario\n")
    cols = [c for c in ("scenario", "n_runs", "u_pct_median", "v_pct_median",
                        "tightness_median", "median_u_R_median",
                        "median_wage_ratio_median", "coverage_0.25_median")
            if c in grouped.columns]
    if cols:
        g = grouped[cols].copy()
        g.columns = [c.replace("_median", "").replace("_pct", " %") for c in cols]
        A(g.to_markdown(index=False, floatfmt=".3f") + "\n")

    if "share_q_below_0.4" in df.columns:
        A("## Passform vid anställning\n")
        x = pd.to_numeric(df["share_q_below_0.4"], errors="coerce").dropna()
        q10 = pd.to_numeric(df.get("p10_q_hire"), errors="coerce").dropna()
        if len(x):
            A(f"Andel anställningar med konkurrenskraft under 0,40: "
              f"{100*x.median():.1f} %"
              + (f" (p10 för q: {q10.median():.2f})" if len(q10) else "") + ".\n")
            A("Låg konkurrenskraft är inte i sig ett fel: i jobb med lågt krav "
              "(diskaren) är produktiviteten full ändå.\n")
        if "share_lowq_in_demanding" in df.columns:
            y = pd.to_numeric(df["share_lowq_in_demanding"], errors="coerce").dropna()
            n = pd.to_numeric(df.get("n_demanding_hires"), errors="coerce").dropna()
            if len(y):
                A(f"**Det avslöjande måttet:** andel anställningar i krävande jobb "
                  f"(r ≥ 0,6) med konkurrenskraft under 0,40: {100*y.median():.1f} % "
                  f"(av {int(n.median()) if len(n) else '?'} sådana anställningar). "
                  f"Den ska vara nära noll: annars tillträder folk jobb de inte "
                  f"klarar.\n")

    # Vakansstocken ar det enda stallet u kan roras: U = L - J + V ger
    # u = u_min + V/L exakt, sa u och v ar samma tal tva ganger. Utan
    # varaktigheten gick det inte att se vilken av dem som var for hog.
    if "vacancy_days" in df.columns:
        vd = pd.to_numeric(df["vacancy_days"], errors="coerce").dropna()
        km = pd.to_numeric(df.get("median_commute_km"), errors="coerce").dropna()
        if len(vd):
            A("## Pendling och vakanser\n")
            A(f"Vakansvaraktighet (Littles lag, medelstock delat med flöde): "
              f"**{vd.median():.0f} dagar**"
              + (f", spann {vd.min():.0f}–{vd.max():.0f} över frön" if len(vd) > 1 else "")
              + ". Svensk vakansvaraktighet ligger kring 30–40 dagar.\n")
            A("Eftersom $U = L - J + V$ är $u = u\\_{min} + V/L$ exakt: u och v är "
              "samma tal två gånger, och vakansstocken är det enda som kan "
              "flyttas utan att ändra arbetskraften eller jobbstocken.\n")
            if len(km):
                p90 = pd.to_numeric(df.get("p90_commute_km"), errors="coerce").dropna()
                A(f"Medianpendling: **{km.median():.1f} km**"
                  + (f", p90 {p90.median():.1f} km" if len(p90) else "")
                  + ". Kalibreras mot tabellen `commuting` (SCB:s flöden mellan "
                    "kommuner); inom en enda kommun går pendlingsmekanismen inte "
                    "att pröva, eftersom de högst betalda arbetsgivarna ligger "
                    "centralt.\n")

    # Konkurrensen om vakansen. Utan den gar det inte att skilja "ingen sokte"
    # fran "urvalet var svagt", och det avgor helt olika atgarder.
    if "mean_applicants" in df.columns:
        ma = pd.to_numeric(df["mean_applicants"], errors="coerce").dropna()
        un = pd.to_numeric(df.get("share_uncontested"), errors="coerce").dropna()
        if len(ma):
            A("## Konkurrens om vakansen\n")
            A(f"Sökande per tillsatt vakans: **{ma.median():.2f}** i medel"
              + (f", och {100*un.median():.0f} % av tillsättningarna hade bara "
                 f"en sökande" if len(un) else "") + ".\n")
            A("Urvalet doserar konkurrenskraften en andra gång, så det "
              "accepterade avståndet blir Rayleigh med skala $\\sigma/\\sqrt{n}$: "
              "väntad median $u_R = 1{,}03/\\sqrt{n}$ task-radier. En vakans med "
              "en enda sökande har inget urval alls, och den lokaliteten "
              "uteblir därför just där ingen söker.\n")

    def _kol(namn):
        """Alltid en Series. pd.to_numeric(None) ger np.float64 nan, och
        rapporten kraschade på .dropna() när kolumnen saknades helt."""
        v = df[namn] if namn in df.columns else None
        if v is None:
            return pd.Series(dtype=float)
        return pd.to_numeric(v, errors="coerce").dropna()

    jr = _kol("job_to_job_rate")
    if len(jr):
        A("## Stegen\n")
        wg = _kol("job_to_job_wage_gain")
        sh = _kol("share_hires_from_employment")
        A(f"Jobbyten per år, andel av anställda: **{100*jr.median():.1f} %**"
          + (f", medianlönevinst per byte {100*(wg.median()-1):+.1f} %" if len(wg) else "")
          + ". Svensk nivå ligger kring tio procent. Byten och vinster är det "
            "som skiljer en för snabb stege ($\\kappa = \\lambda_1/\\delta$) från "
            "en felförankrad $\\Pi$: många byten med stora vinster är det "
            "förra, få med små det senare.\n")
        if len(sh):
            A(f"Andel tillsättningar som gick till en redan anställd sökande: "
              f"**{100*sh.median():.0f} %**.")
            qe = _kol("q_applicants_employed")
            qu = _kol("q_applicants_unemployed")
            if len(qe) and len(qu):
                A(f" Median $q$ bland sökande: {qe.median():.2f} anställda mot "
                  f"{qu.median():.2f} arbetslösa. Divergerar de tränger "
                  "restpoolen undan: arbetsgivaren möter inte arbetskraften "
                  "utan dem som ännu inte matchats.")
            A("\n")
        eu = _kol("entry_wage_ratio_from_unemployment")
        ej = _kol("entry_wage_ratio_job_to_job")
        d1 = _kol("days_to_first_step_median")
        s1 = _kol("share_first_step_within_year")
        st = _kol("share_unemployed_hires_that_step")
        if len(eu) and len(ej):
            A(f"Ingångslön relativt yrkets $\\Pi_o$: **{eu.median():.3f}** ur arbetslöshet, "
              f"**{ej.median():.3f}** vid byte."
              + (f" Av dem som anställs ur arbetslöshet byter {100*st.median():.0f} % "
                 f"senare under körningen, median {d1.median():.0f} dagar efter tillträdet, "
                 f"{100*s1.median():.0f} % inom ett år." if len(d1) else "")
              + " Är rabatten ur arbetslöshet stor och nästa steg snabbt är stegen "
                "det första steget efter arbetslöshet, och bytesfrekvensen sätts av "
                "ingångslönen -- inte av söktakten (svepet 0089).\n")
        md = {k: _kol(f"move_{k}_mean") for k in
              ("d_occ", "d_eta", "d_fit", "d_revision", "gain")}
        if len(md["gain"]):
            A("Bytespremien delad i sina tre källor, mellan två anställningar för "
              "samma individ ($\\log w = \\log \\Pi_o + \\eta + \\theta\\log p$): "
              f"yrkets pris **{100*md['d_occ'].median():+.1f} %**, arbetsgivareffekten "
              f"**{100*md['d_eta'].median():+.1f} %**, passformen "
              f"**{100*md['d_fit'].median():+.1f} %**. Revisionen gav under "
              f"anställningen **{100*md['d_revision'].median():+.1f} %**, och kvar som "
              f"bytespremie blir **{100*md['gain'].median():+.1f} %**. Växer passformen "
              "inuti anställningen utan att revisionen betalar den är `beta_q` spaken; "
              "dominerar arbetsgivareffekten är det `employer_wage_sd` och urvalet.\n")
        se = _kol("searches_per_year_employed")
        su = _kol("searches_per_year_unemployed")
        if len(se) and len(su):
            A(f"Sökningar per personår: **{se.median():.2f}** anställda, "
              f"**{su.median():.2f}** arbetslösa. Faktorn sätts mot AKU:s "
              "ombytessökande, ungefär en sökepisod per anställd och år "
              "(nivån ska verifieras mot AM0401); amerikansk nivå är ~2.6 "
              "(Faberman m.fl. 2022).\n")
        vo = _kol("open_vacancy_days")
        vop = _kol("v_open_pct")
        if len(vo) and len(vop):
            A(f"Utan de UTLOVADE positionerna -- tillsatta men ej tillträdda, som "
              f"SCB:s vakansbegrepp inte räknar -- är vakansgraden **{vop.median():.2f} %** "
              f"och varaktigheten **{vo.median():.0f} dagar**. Skillnaden mot talen ovan "
              "är uppsägningstiden. Identiteten $U = L - J + V$ använder alla obesatta "
              "positioner och är oberörd.\n")
        vf = _kol("wait_first_applicant_median")
        vb = _kol("vacancy_age_at_decision_median")
        vu = _kol("vacancy_days_share_unfilled")
        if len(vf) and len(vb):
            A(f"Vakansens liv, delat: **{vf.median():.0f} dagar** väntan på den första "
              f"sökanden, sedan annonsfönstret, och **{vb.median():.0f} dagar** totalt "
              "fram till beslutet; resten fram till tillträdet är tillträdesfördröjning "
              "och uppsägningstid."
              + (f" Av alla vakansdagar tillbringas **{100*vu.median():.0f} %** i "
                 "positioner som aldrig tillsätts." if len(vu) else "")
              + " Stocken är flöde gånger varaktighet, så det är dessa poster och "
                "ingenting annat som sätter vakansgraden.\n")
        sd = _kol("start_delay_median")
        sdu = _kol("start_delay_median_unemployed")
        sde = _kol("start_delay_median_employed")
        she = _kol("share_hires_employed")
        if len(sd):
            A(f"Från beslut till tillträde: median **{sd.median():.0f} dagar** — "
              + (f"{sdu.median():.0f} för den som kommer ur arbetslöshet, " if len(sdu) else "")
              + (f"{sde.median():.0f} för den som har uppsägningstid, och " if len(sde) else "")
              + (f"{100*she.median():.0f} % av tillsättningarna är av det senare slaget. "
                 if len(she) else "")
              + "Väntan, fönstret, fördröjningen och de aldrig tillsatta ska summera till "
                "vakansens varaktighet; gör de inte det är en av posterna fel.\n")
        va = _kol("vacancy_age_median")
        vp = _kol("vacancy_age_p90")
        if len(va):
            A(f"Vakansernas ålder vid tillsättning: median **{va.median():.0f}** "
              f"dagar" + (f", p90 {vp.median():.0f}" if len(vp) else "")
              + ". En växande svans säger att stocken består av samma "
                "positioner, inte av flöde.\n")

    if "flow_w_p90p10" in df.columns:
        r9 = pd.to_numeric(df["flow_w_p90p10"], errors="coerce").dropna()
        sd = pd.to_numeric(df.get("flow_sd_log_w"), errors="coerce").dropna()
        ev = pd.to_numeric(df.get("employer_var_share"), errors="coerce").dropna()
        if len(r9):
            A("## Lönefördelning\n")
            A(f"**Global**, alla yrken, lön vid anställning: P90/P10 "
              f"**{r9.median():.2f}**"
              + (f", sd(log w) {sd.median():.3f}" if len(sd) else "")
              + ". Lönestrukturstatistikens P90/P10 för hela arbetsmarknaden "
                "var 2,20 för 2025, men det måttet gäller BESTÅNDET medan "
                "detta är flödet: nyanställda är ett skevt urval, och utan "
                "lönetillväxt med tjänstetid saknas det som skiljer stock "
                "från flöde. Beståndets tvärsnitt loggas årsvis (stock_w_*).\n")
            sa = pd.to_numeric(df.get("stock_share_above_pi"), errors="coerce").dropna()
            if len(sa):
                A(f"Andel av **beståndet** över sitt eget yrkes $\\Pi$: "
                  f"**{100*sa.median():.0f} %**. Är $\\Pi$ yrkets median ska den "
                  "vara 50: det är ett definitionsvillkor och ingen "
                  "formhypotes. Flödets andel är en ANNAN storhet och ska "
                  "ligga högre, eftersom den som just valts ut av "
                  "arbetsgivaren har högre passform än yrkets median.\n")
            if len(ev):
                A(f"Andel av variansen i log lön som ligger i **arbetsgivaren**: "
                  f"{100*ev.median():.0f} %. AKM-dekompositioner ger 10–20 "
                  "procent; det är kontrollen på `employer_wage_sd`.\n")
            A("Spridningen **inom yrke** är en annan storhet och står per "
              "kvartil i `r_req` i figurens datafil. Den ska växa med "
              "kravnivån, $\\sigma = \\theta k r_j \\sigma_{\\log q}$, och "
              "jämförs med SCB:s percentiler per SSYK.\n")

    A("## Mot referensvärden\n")
    A("| Storhet | Modell (median) | Spridning över frön | Referens | Källa |")
    A("|---|---|---|---|---|")
    for key, ref, src in (("median_u_R", REF["median_u_R"],
                           "papper 2, inom delsystem"),
                          ("u_pct", REF["u_pct"], "svensk arbetslöshet"),
                          ("v_pct", REF["v_pct"], "svensk vakansgrad")):
        if key not in df.columns:
            continue
        x = pd.to_numeric(df[key], errors="coerce").dropna()
        if x.empty:
            continue
        spread = f"{x.min():.2f}–{x.max():.2f}" if len(x) > 1 else "—"
        A(f"| {key} | {_fmt(float(x.median()))} | {spread} | {ref} | {src} |")
    A("")

    # Korrelationen mellan täckning och utfall är bara meningsfull ÖVER
    # scenarier. Med flera frön av samma scenario varierar täckningen bara med
    # slumpen, och en korrelation mäter då brus. En körning gav -0.37 och -0.60
    # på sex frön av samma kommun, vilket såg ut som stöd för hypotesen.
    n_scen = df["scenario"].nunique() if "scenario" in df.columns else 1
    if "coverage_0.25" in df.columns:
        A("## Täckning mot utfall\n")
        if n_scen < 3:
            A(f"Utelämnas: {n_scen} scenario i materialet. Sambandet mellan "
              f"uppgiftsrummets täckning och utfall kan bara mätas ÖVER "
              f"scenarier. Med flera frön av samma scenario varierar täckningen "
              f"bara med slumpen, och en korrelation mäter brus.\n")
        else:
            A("Hypotesen förutsäger negativ korrelation: ett tjockare "
              "uppgiftsrum ger lägre arbetslöshet och kortare omställningar. "
              "Korrelationen beräknas på scenariomedianer, så att spridning "
              "mellan frön inte räknas som observationer.\n")
            med = grouped.set_index(by)
            A("| Utfall | Spearman mot C(0.25) | n scenarier |")
            A("|---|---|---|")
            for col in ("u_pct", "median_u_R", "tightness"):
                c1, c2 = "coverage_0.25_median", f"{col}_median"
                if c1 not in med.columns or c2 not in med.columns:
                    continue
                sub = med[[c1, c2]].apply(pd.to_numeric, errors="coerce").dropna()
                if len(sub) >= 3:
                    r = sub.corr(method="spearman").iloc[0, 1]
                    A(f"| {col} | {('%+.2f' % r) if np.isfinite(r) else '—'} "
                      f"| {len(sub)} |")
        A("")

    if "seed" in df.columns and df["seed"].nunique() > 1:
        A("## Spridning över frön\n")
        A("Skillnaden mellan frön är den tröskel en modelländring måste "
          "överstiga för att räknas som en effekt och inte som brus.\n")
        A("| Storhet | Median | Min | Max | Spann |")
        A("|---|---|---|---|---|")
        for key in ("median_u_R", "u_pct", "v_pct", "median_wage_ratio",
                    "tightness", "share_q_below_0.4"):
            if key not in df.columns:
                continue
            x = pd.to_numeric(df[key], errors="coerce").dropna()
            if len(x) > 1:
                A(f"| {key} | {x.median():.3f} | {x.min():.3f} | {x.max():.3f} "
                  f"| {x.max()-x.min():.3f} |")
        A("")

    if figdir:
        A("## Figurer\n")
        for f in sorted(os.listdir(figdir)):
            if f.endswith(".pdf"):
                A(f"- `{f}` (data och manifest bredvid)")
        A("")

    A("## Körningar\n")
    show = [c for c in ("run", "scenario", "seed", "commit", "years", "u_pct",
                        "v_pct", "median_u_R", "n_cps_sample") if c in df.columns]
    # disable_numparse: tabulate läste commit-hashen 19534e35 som talet
    # 1.9534e39 och skrev ut fyrtio siffror i tabellen.
    A(df[show].to_markdown(index=False, floatfmt=".2f", disable_numparse=True) + "\n")

    path = os.path.join(out, "report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Sparad: {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--since", default=None, help="bara körningar från denna commit")
    ap.add_argument("--out", default=os.path.join(ROOT, "analysis"))
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()

    outdir = os.path.join(ROOT, "output")
    runs = a.runs or (runs_under(outdir) if a.all else [])
    if not runs:
        cand = runs_under(outdir)
        if not cand:
            raise SystemExit("Inga körningar under output/.")
        runs = [max(cand, key=os.path.getmtime)]
        print(f"(använder senaste: {os.path.basename(runs[0])})\n")

    print(f"Exporterar tabeller för {len(runs)} körningar ...")
    for rd in runs:
        try:
            export(rd)
        except Exception as e:
            print(f"  hoppar över {os.path.basename(rd)}: {type(e).__name__}: {e}")

    df = collect_runs(runs)
    if df.empty:
        raise SystemExit("Inga körningar kunde läsas.")
    if a.since and "commit" in df.columns:
        keep = df["commit"] == a.since[:8]
        print(f"Filtrerat på commit {a.since[:8]}: {int(keep.sum())} av {len(df)}")
        df = df[keep]
        runs = [r for r in runs if os.path.basename(str(r).rstrip("/"))
                in set(df["run"])]
        if df.empty:
            raise SystemExit("Inga körningar matchade filtret.")

    os.makedirs(a.out, exist_ok=True)
    df.to_csv(os.path.join(a.out, "runs.csv"), index=False)
    by = "scenario" if "scenario" in df.columns else "run"
    grouped = group_stats(df, by=by)
    grouped.to_csv(os.path.join(a.out, "by_scenario.csv"), index=False)
    print(f"Sparad: {os.path.join(a.out, 'runs.csv')}")
    print(f"Sparad: {os.path.join(a.out, 'by_scenario.csv')}")

    figdir = None
    if not a.no_figures:
        import scripts.figures as F  # noqa
        figdir = os.path.join(a.out, "figures")
        os.makedirs(figdir, exist_ok=True)
        F.fig_mobility(runs, figdir)
        F.fig_competence(figdir)
        F.fig_coverage(runs, figdir)
        F.fig_tenure(figdir)
        F.fig_wages(runs, figdir)
        F.fig_commute(runs, figdir)

    write_report(df, grouped, a.out, runs, figdir, by=by)


if __name__ == "__main__":
    main()
