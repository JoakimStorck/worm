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
            senaste = (max(run_dirs, key=os.path.getmtime) if run_dirs else None)
            rh = riktningsharmonik(senaste) if senaste else None
            if rh:
                rel_mod = rh["amplitud"] / rh["medel"] if rh["medel"] else float("nan")
                A("\n**Rekryteringstidens riktning i uppgiftsrummet.** Vakansålder "
                  "vid tillsättning anpassad till $T = a + \\chi(b\\cos\\xi + "
                  "c\\sin\\xi)$ -- samma första harmonik som papprets "
                  "löneekvation och som SCB:s rekryteringstid per bransch. "
                  "Modellen får producera sin egen yta; den matas inte in.\n")
                A("| | modell | SCB 2023 (näringslivet) |")
                A("|---|---|---|")
                A(f"| toppriktning | {rh['topp']:.0f}° | {SCB_REKRYTERING_TOPP:.0f}° "
                  f"(pappret, lön: 89.5°) |")
                A(f"| amplitud, dagar per enhet $\\chi$ | {rh['amplitud']:.0f} | "
                  f"{SCB_REKRYTERING_AMPLITUD:.0f} |")
                A(f"| amplitud relativt nivån | {rel_mod:.2f} | "
                  f"{SCB_REKRYTERING_AMPLITUD / SCB_REKRYTERING_NIVA:.2f} |")
                A(f"| $R^2$ plan | {rh['R2']:.3f} | 0.834 (n = 11) |")
                A(f"| $R^2$ radiell | {rh['R2_radiell']:.3f} | 0.003 |")
                A(f"| n | {rh['n']} tillsättningar | 11 branscher |")
                avv = ((rh["topp"] - SCB_REKRYTERING_TOPP + 180) % 360) - 180
                if abs(avv) < 30:
                    A(f"\nToppriktningen ligger {abs(avv):.0f}° från SCB:s: "
                      "mekanismen ger rätt riktning, och skillnaden i nivå kan "
                      "kalibreras med en parameter som skalar allt lika.\n")
                else:
                    A(f"\nToppriktningen avviker {abs(avv):.0f}° från SCB:s. "
                      "Mekanismen är fel på ett sätt en nivåkalibrering döljer: "
                      "specificiteten försvårar rekryteringen i fel del av "
                      "rummet.\n")
                A("Vakansålder vid tillsättning är flödesviktad; vakanser som "
                  "aldrig tillsätts syns inte, så talet underskattar. SCB:s tal "
                  "är stock delat med flöde och gäller näringslivet.\n")

            av = arbetsloshetens_varaktighet(senaste) if senaste else None
            if av:
                A("\n**Arbetslöshetens varaktighet.** Pågående perioder vid "
                  "körningens slut. Det är det mått tidskonstanterna i "
                  "löneanspråket ska kalibreras mot: sedan anspråket faller med "
                  "arbetslöshetens LÄNGD är det trögheten som sätter hur länge "
                  "någon står utanför, och därmed stocken.\n")
                A(f"| | modell |")
                A(f"|---|---|")
                A(f"| median | {av['median']:.0f} dagar |")
                A(f"| p90 | {av['p90']:.0f} dagar |")
                A(f"| andel över 6 månader | {100*av['andel_6man']:.0f} % |")
                A(f"| andel över 12 månader | {100*av['andel_12man']:.0f} % |")
                A(f"| n | {av['n']} arbetslösa |")
                if av["utan_klocka"]:
                    A(f"\n{av['utan_klocka']} arbetslösa saknar startpunkt -- de "
                      "har varit det sedan uppstarten och har ingen uppmätt "
                      "längd.\n")
                A("\nMåttet är censurerat: pågående perioder, inte avslutade, "
                  "så de långa underskattas. Arbetsförmedlingens andel "
                  "inskrivna över sex respektive tolv månader räknar också "
                  "pågående inskrivningar och är därmed jämförbar.\n")

            mr = misslyckade_rekryteringar(senaste) if senaste else None
            if mr and mr["n_lang"]:
                A("\n**Misslyckade rekryteringar.** Positioner lediga vid "
                  "körningens slut, äldre än 180 dagar. Det är svansen som "
                  "lyfter Littles lag från de tillsatta vakansernas 50-80 dagar "
                  "till 150: en vakans i modellen står och annonseras om tills "
                  "någon tar den, och ingen mekanism låter arbetsgivaren ge "
                  "upp, hyra in eller omfördela.\n")
                A(f"| | värde |")
                A(f"|---|---|")
                A(f"| lediga positioner vid slutet | {mr['n_lediga']} |")
                A(f"| varav äldre än 180 dagar | {mr['n_lang']} ({100*mr['andel_lang']:.0f} %) |")
                A(f"| deras medianålder | {mr['alder_median_lang']:.0f} dagar |")
                A(f"| andel som aldrig fått en sökande | {100*mr['aldrig_sokt_lang']:.0f} % |")
                A(f"| tomma fönster per position, median | {mr['tomma_median_lang']:.0f} |")
                A(f"| kravnivå r_req, median: gamla / övriga | "
                  f"{mr['r_req_lang']:.2f} / {mr['r_req_kort']:.2f} |")
                if "andel_norr_lang" in mr:
                    A(f"| andel i norra halvplanet: gamla / alla lediga | "
                      f"{100*mr['andel_norr_lang']:.0f} % / {100*mr['andel_norr_alla']:.0f} % |")
                if "storlek_median_lang" in mr:
                    A(f"| arbetsgivarstorlek, median: gamla / alla | "
                      f"{mr['storlek_median_lang']:.0f} / {mr['storlek_median_alla']:.0f} |")
                if "per_kommun" in mr:
                    A("\nGamla positioner per kommun, mot kommunens andel av alla lediga:\n")
                    A("| kommun | >180 dagar | andel av kommunens lediga |")
                    A("|---|---|---|")
                    for k, n in sorted(mr["per_kommun"].items()):
                        tot = mr["stock_per_kommun"].get(k, 0)
                        A(f"| {k} | {n} | {100*n/tot:.0f} % |" if tot else f"| {k} | {n} | – |")
                A("\nStiger kravnivån och andelen i norr bland de gamla är svansen "
                  "tunnhet i uppgiftsrummet. Är andelen som aldrig fått en "
                  "sökande hög är positionerna utom räckhåll för alla, och då "
                  "hjälper inga fler fönster. Att sänka r_req är ingen lösning: "
                  "det är kompetensgränsen, och att sänka den låter vem som "
                  "helst göra vad som helst.\n")
            if len(km):
                p90 = pd.to_numeric(df.get("p90_commute_km"), errors="coerce").dropna()
                A(f"Medianpendling: **{km.median():.1f} km**"
                  + (f", p90 {p90.median():.1f} km" if len(p90) else "")
                  + ". Referensen är tabellen `commuting` (SCB:s flöden mellan "
                    "kommuner) när den finns laddad; inom en enda kommun går "
                    "pendlingsmekanismen inte att pröva, eftersom de högst "
                    "betalda arbetsgivarna ligger centralt.\n")

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
        hinkar = ["0-40", "40-90", "90-180", "180-inf"]
        andel = {h: _kol(f"vacancy_stock_share_{h}") for h in hinkar}
        krav = {h: _kol(f"vacancy_r_req_{h}") for h in hinkar}
        if all(len(andel[h]) for h in hinkar):
            A("Vakansstockens ålder, ur den månatliga folkräkningen (som till skillnad "
              "från väntetiden ovan också ser de positioner som ALDRIG får en sökande): "
              + ", ".join(f"**{100*andel[h].median():.0f} %** {h} dagar" for h in hinkar)
              + (". Medelkravnivå r_req: "
                 + ", ".join(f"{krav[h].median():.2f} ({h})" for h in hinkar if len(krav[h]))
                 if any(len(krav[h]) for h in hinkar) else "")
              + ". Stiger kravet med åldern är svansen tunnhet i uppgiftsrummet; är den "
                "jämn över kravnivåer ligger den i hur startbeståndets yrken möter jobbens.\n")
        wq = [_kol(f"wait_first_applicant_mean_q{i}") for i in (1, 2, 3, 4)]
        if all(len(x) for x in wq):
            A("Väntan på första sökanden per kravkvartil: "
              + ", ".join(f"{x.median():.0f} d" for x in wq)
              + " (lägsta till högsta r_req). Måttet är censurerat: en vakans utan sökande "
                "loggar ingen väntetid alls.\n")
        cm = _kol("share_hires_cross_municipality")
        if len(cm) and cm.max() > 0:
            ci = _kol("commute_km_median_cross"); cw = _kol("commute_km_median_within")
            A(f"Pendling över kommungräns: **{100*cm.median():.1f} %** av tillsättningarna "
              "går till ett jobb i en annan kommun än individens"
              + (f", med medianpendling {ci.median():.0f} km mot {cw.median():.0f} km inom "
                 "kommunen" if len(ci) and len(cw) else "")
              + ".\n")
            kommuner = set()
            for rad in df.get("municipalities", pd.Series(dtype=str)).dropna():
                kommuner.update(str(rad).split(","))
            scb, scb_ar = scb_pendlingsandel(kommuner)
            if scb is not None:
                A(f"SCB:s motsvarande andel för samma kommuner är "
                  f"**{100*scb:.1f} %**"
                  + (f" ({scb_ar})" if scb_ar else "")
                  + f", alltså en kvot modell/observerat på {cm.median()/scb:.2f}. "
                    "Talen är inte samma sak: modellens andel gäller "
                    "TILLSÄTTNINGAR under körningen, SCB:s gäller STOCKEN av "
                    "sysselsatta. Ett flöde kan rimligen avvika från den stock "
                    "det bygger upp, men storleksordningen ska stämma.\n")
            else:
                A("SCB:s pendlingsmatris saknas i databasen, så andelen har "
                  "ingen observerad motsvarighet att ställas mot. Ladda den med "
                  "`python -m core.database.load_commuting_matrix <SCB-fil>`; "
                  "till dess är `commute_cost_per_km` satt, inte kalibrerad.\n")

            # --- Arbetslöshet per kommun, modell mot SCB ---
            # Senaste körningen: arbetslöshet per kommun är ett tillstånd i
            # slutläget, inte ett medelvärde över körningar.
            senaste = (max(run_dirs, key=os.path.getmtime) if run_dirs else None)
            mod_u = arbetsloshet_per_kommun(senaste) if senaste else None
            scb_u = scb_arbetsloshet(kommuner) if kommuner else None
            if mod_u is not None and scb_u is not None:
                A("\n**Arbetslöshet per kommun.** Modellens tal är andel av "
                  "arbetskraften i slutläget; SCB:s avser 20-65 år och "
                  "registerbaserad status. Åldersintervallen skiljer sig, så "
                  "det jämförbara är rangordningen och spridningen, inte "
                  "nivån. Modellens arbetslösa är dessutom avgränsade till "
                  "scenariots kommuner: den som i verkligheten pendlar ut ur "
                  "området finns inte i modellen.\n")
                A("| kommun | modell | SCB | kvot |")
                A("|---|---|---|---|")
                for kod in sorted(scb_u.index):
                    if kod not in mod_u.index:
                        continue
                    m = float(mod_u.loc[kod, "u_rate"])
                    v = float(scb_u.loc[kod, "u_rate"])
                    A(f"| {kod} | {m:.1f} % | {v:.2f} % | {m / v:.1f} |")
                ordn_m = list(mod_u["u_rate"].sort_values().index)
                ordn_s = list(scb_u["u_rate"].sort_values().index)
                gem = [k for k in ordn_m if k in ordn_s]
                if gem == [k for k in ordn_s if k in ordn_m]:
                    A("\nRangordningen stämmer med SCB:s.\n")
                else:
                    A(f"\nRangordningen skiljer sig: modellen ger "
                      f"{' < '.join(gem)}, SCB "
                      f"{' < '.join(k for k in ordn_s if k in ordn_m)}.\n")
            elif mod_u is not None:
                A("\nSCB:s arbetsmarknadsstatus saknas i databasen, så "
                  "arbetslösheten per kommun har ingen observerad "
                  "motsvarighet. Ladda den via `python scripts/create_database.py`.\n")
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


def arbetsloshet_per_kommun(run_dir):
    """Modellens arbetslöshet per kommun, som andel av ARBETSKRAFTEN.

    Individtabellen är hela befolkningen: status not_in_labor_force är över
    halva den. Andelen av befolkningen är därför inte jämförbar med SCB:s tal
    och skiljer sig med en faktor två från andelen av arbetskraften -- en
    förväxling som en gång fick modellens arbetslöshet att se ut att ligga
    nära verklighetens när den låg tre till sex gånger över.
    """
    p = os.path.join(run_dir, "final_state_individuals.csv")
    if not os.path.isfile(p):
        return None
    ind = pd.read_csv(p)
    if "status" not in ind.columns:
        return None
    ind["kom"] = ind["individual_id"].astype(str).str.split("_i").str[0]
    t = ind.groupby("kom")["status"].value_counts().unstack(fill_value=0)
    for k in ("employed", "unemployed"):
        if k not in t.columns:
            t[k] = 0
    t["u_rate"] = 100 * t["unemployed"] / (t["employed"] + t["unemployed"]).replace(0, np.nan)
    return t[["employed", "unemployed", "u_rate"]]


def scb_arbetsloshet(koder, db_path="data/worm.sqlite3"):
    """SCB:s arbetsmarknadsstatus per kommun, eller None om tabellen saknas."""
    import sqlite3
    if not os.path.isfile(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM labour_market_status", conn)
        conn.close()
    except Exception:
        return None
    if df.empty:
        return None
    df["municipal_code"] = (df["municipal_code"].astype(str).str.strip()
                            .str.zfill(4))
    df = df[df["municipal_code"].isin({str(k).strip().zfill(4) for k in koder})]
    return df.set_index("municipal_code") if not df.empty else None


# Toppriktning och amplitud för rekryteringstidens första harmonik i SCB:s
# data, ur scripts/rekryteringstid_mot_uppgiftsrum.py på TAB4307 för 2023:
#   T = 47.7 + chi * (2.2 cos xi + 156.5 sin xi), R2 0.834, n = 11 branscher.
# Samma funktionsform som papprets löneekvation (Eq. 4), vars topp ligger på
# 89.5 grader. Talen gäller NÄRINGSLIVET och är en engångsmätning; körs
# skriptet om med nya SCB-data ska de uppdateras här.
SCB_REKRYTERING_TOPP = 89.2
SCB_REKRYTERING_AMPLITUD = 156.5
SCB_REKRYTERING_NIVA = 47.7


def arbetsloshetens_varaktighet(run_dir, t_slut=None):
    """Hur länge de arbetslösa har varit det, vid körningens slut.

    TIDSKONSTANTERNA SKA MÄTAS MOT DET HÄR, inte mot arbetslöshetsnivån.
    Sedan anspråket faller med arbetslöshetens längd är det trögheten som
    sätter hur länge någon står utanför, och därmed stocken: u = u_min + V/L.
    Att kalibrera reservation_half_days mot nivån vore att justera en
    tidskonstant efter ett utfall den bara delvis bestämmer.

    Måttet är CENSURERAT: pågående perioder, inte avslutade. Det underskattar
    därför de långa, eftersom den som fått jobb inte längre syns. Jämförelsen
    mot Arbetsförmedlingens andel inskrivna över sex respektive tolv månader
    har samma karaktär -- den räknar också pågående inskrivningar -- så de är
    jämförbara storheter.
    """
    p = os.path.join(run_dir, "final_state_individuals.csv")
    if not os.path.isfile(p):
        return None
    ind = pd.read_csv(p)
    if "unemployed_since" not in ind.columns or "status" not in ind.columns:
        return None
    if t_slut is None:
        from core.analysis.eventlog import read_events
        try:
            t_slut = max((float(r["time"]) for r in read_events(run_dir)), default=np.nan)
        except Exception:
            return None
    if not np.isfinite(t_slut):
        return None
    arbl = ind[ind["status"] == "unemployed"].copy()
    arbl["dagar"] = t_slut - pd.to_numeric(arbl["unemployed_since"], errors="coerce")
    d = arbl["dagar"].dropna()
    if len(d) < 20:
        return None
    return {"n": int(len(d)), "median": float(d.median()),
            "andel_6man": float((d >= 182.6).mean()),
            "andel_12man": float((d >= 365.25).mean()),
            "p90": float(d.quantile(0.9)),
            "utan_klocka": int(len(arbl) - len(d))}


def misslyckade_rekryteringar(run_dir, t_slut=None):
    """Positioner som inte fylls: hur många, hur gamla, vilka.

    SCB:s rekryteringstid är stock delat med flöde, och modellens 150 dagar
    mot SCB:s 32 sitter inte i de tillsatta vakanserna -- de lever 50-80
    dagar -- utan i svansen: 39 procent av stocken är äldre än 180 dagar.
    Vakansen i modellen är passiv, den står och annonseras om tills någon
    tar den, och ingenting låter arbetsgivaren ge upp. Innan något sådant
    införs ska svansen beskrivas: vilka positioner det är, om de alls får
    sökande, hur många gånger fönstret stängts tomt, och var i uppgiftsrummet
    och geografin de sitter.

    Att sänka r_req generellt är INTE en lösning: r_req är kompetensgränsen,
    och att sänka den låter en fastighetsmäklare göra en kirurgs jobb. Det
    arbetsgivare kallar sänkta krav på erfarenhet är en marginaljustering
    inom samma kompetens.
    """
    from core.analysis.eventlog import read_events
    p = os.path.join(run_dir, "final_state_jobs.csv")
    if not os.path.isfile(p):
        return None
    jobb = pd.read_csv(p)
    if "vacant_since" not in jobb.columns:
        return None
    try:
        h = read_events(run_dir)
    except Exception:
        h = []
    if t_slut is None:
        t_slut = max((float(r["time"]) for r in h), default=np.nan)
    if not np.isfinite(t_slut):
        return None

    aktiv = jobb.get("active", True)
    aktiv = aktiv.fillna(False).astype(bool) if hasattr(aktiv, "fillna") else aktiv
    pend = jobb.get("pending", False)
    pend = pend.fillna(False).astype(bool) if hasattr(pend, "fillna") else pend
    ledig = jobb[jobb["individual_id"].isna() & aktiv & ~pend].copy()
    if ledig.empty:
        return None
    ledig["alder"] = t_slut - pd.to_numeric(ledig["vacant_since"], errors="coerce")
    ledig = ledig.dropna(subset=["alder"])
    ledig["job_id"] = ledig["job_id"].astype(str)

    # Misslyckade fönster och ansökningar per position, ur loggen.
    tomma, sokt = {}, {}
    for r in h:
        j = r.get("job_id")
        if not j:
            continue
        d = r.get("event_detail")
        if d == "vacancy_closed_unfilled":
            tomma[j] = tomma.get(j, 0) + 1
        elif d == "advert_opened":
            sokt[j] = sokt.get(j, 0) + 1
    ledig["tomma_fonster"] = ledig["job_id"].map(tomma).fillna(0).astype(int)
    ledig["annonser"] = ledig["job_id"].map(sokt).fillna(0).astype(int)

    lang = ledig[ledig["alder"] >= 180]
    ut = {"n_lediga": int(len(ledig)), "n_lang": int(len(lang)),
          "andel_lang": float(len(lang) / len(ledig)),
          "alder_median_lang": float(lang["alder"].median()) if len(lang) else np.nan,
          "aldrig_sokt_lang": float((lang["annonser"] == 0).mean()) if len(lang) else np.nan,
          "tomma_median_lang": float(lang["tomma_fonster"].median()) if len(lang) else np.nan,
          "r_req_lang": float(pd.to_numeric(lang.get("r_req"), errors="coerce").median())
              if len(lang) and "r_req" in lang.columns else np.nan,
          "r_req_kort": float(pd.to_numeric(ledig[ledig["alder"] < 180].get("r_req"),
                                            errors="coerce").median())
              if "r_req" in ledig.columns else np.nan}
    if "municipal_code" in lang.columns and len(lang):
        ut["per_kommun"] = (lang["municipal_code"].astype(str).str.zfill(4)
                            .value_counts().to_dict())
        ut["stock_per_kommun"] = (ledig["municipal_code"].astype(str).str.zfill(4)
                                  .value_counts().to_dict())
    if "y_occ" in lang.columns and len(lang):
        ut["andel_norr_lang"] = float((pd.to_numeric(lang["y_occ"], errors="coerce") > 0).mean())
        ut["andel_norr_alla"] = float((pd.to_numeric(ledig["y_occ"], errors="coerce") > 0).mean())
    if "employer_size" in lang.columns and len(lang):
        ut["storlek_median_lang"] = float(pd.to_numeric(lang["employer_size"],
                                                        errors="coerce").median())
        ut["storlek_median_alla"] = float(pd.to_numeric(ledig["employer_size"],
                                                        errors="coerce").median())
    return ut


def riktningsharmonik(run_dir):
    """Rekryteringstidens första harmonik i uppgiftsrummet, ur körningen.

    VARFÖR DET ÄR ETT TEST OCH INTE EN INMATNING. Rekryteringstiden är ett
    utfall av matchningen, och att mata in SCB:s yta vore att ersätta
    mekanismen med en uppslagstabell -- rätt siffra, ingen härledning. Lönerna
    behandlas annorlunda med rätta: de är priser en enskild matchning tar för
    givna. Här får modellen i stället producera sin egen yta, och den ställs
    mot SCB:s.

    Varje anställning ger en observation: vakansens ålder vid tillsättning
    och jobbets position. Anpassningen är samma plan som mot SCB,

        T = a + chi * (b cos xi + c sin xi) = a + b x_occ + c y_occ,

    men på tusentals oberoende tillsättningar i stället för elva branscher.

    Vakansålder vid tillsättning är flödesviktad varaktighet; SCB:s
    rekryteringstid är stock delat med flöde. Under stationaritet är de lika,
    och avvikelsen -- vakanser som ALDRIG tillsätts syns inte här -- går åt
    känt håll: talet underskattar.
    """
    from core.analysis.eventlog import read_events
    try:
        h = read_events(run_dir)
    except Exception:
        return None
    rader = [(r.get("job_id"), r.get("vacancy_age_days"))
             for r in h if r.get("event") == "start_job"
             and str(r.get("is_bootstrap", "")).lower() not in ("true", "1")
             and not str(r.get("event_detail") or "").startswith("job_gone")]
    if not rader:
        return None
    d = pd.DataFrame(rader, columns=["job_id", "dagar"])
    d["dagar"] = pd.to_numeric(d["dagar"], errors="coerce")
    d = d.dropna()
    if d.empty:
        return None

    jobb = []
    for namn in ("initial_state_jobs.csv", "final_state_jobs.csv"):
        pth = os.path.join(run_dir, namn)
        if os.path.isfile(pth):
            jobb.append(pd.read_csv(pth, usecols=lambda c: c in
                                    ("job_id", "x_occ", "y_occ", "chi", "xi")))
    if not jobb:
        return None
    jobb = pd.concat(jobb).drop_duplicates("job_id", keep="last")
    jobb["job_id"] = jobb["job_id"].astype(str)
    d["job_id"] = d["job_id"].astype(str)
    d = d.merge(jobb, on="job_id", how="inner").dropna(subset=["x_occ", "y_occ"])
    if len(d) < 30:
        return None

    X = np.column_stack([np.ones(len(d)), d["x_occ"], d["y_occ"]])
    y = d["dagar"].to_numpy(dtype=float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ beta
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    a, b, c = beta
    topp = float(np.degrees(np.arctan2(c, b)) % 360)
    amp = float(np.hypot(b, c))
    # Radiell jämförelse: förklarar chi något utan riktning? Pappret säger nej
    # för lön, SCB säger nej för rekryteringstid.
    Xr = np.column_stack([np.ones(len(d)), d["chi"]])
    br, *_ = np.linalg.lstsq(Xr, y, rcond=None)
    r2_rad = 1 - ((y - Xr @ br) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return {"n": int(len(d)), "niva": float(a), "topp": topp, "amplitud": amp,
            "R2": float(r2), "R2_radiell": float(r2_rad),
            "medel": float(y.mean())}


def scb_pendlingsandel(kommuner, db_path="data/worm.sqlite3"):
    """SCB:s andel sysselsatta som arbetar i en ANNAN av körningens kommuner.

    Avgränsad till samma kommuner som scenariot, eftersom modellen bara känner
    dem: en Morabo som pendlar till Falun är i SCB:s tal en pendlare, men i
    modellen finns Falun inte och hon kan inte pendla dit. Jämförs modellens
    andel med SCB:s hela utpendling mäts skillnaden mellan två olika frågor.

    Returnerar (andel, år) eller (None, None) om tabellen saknas.
    """
    import sqlite3
    if not os.path.isfile(db_path):
        return None, None
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM commuting", conn)
        conn.close()
    except Exception:
        return None, None
    if df.empty:
        return None, None
    koder = {str(k).strip().zfill(4) for k in kommuner if str(k).strip()}
    for kol in ("home_municipality", "work_municipality"):
        df[kol] = df[kol].astype(str).str.strip().str.zfill(4)
    df = df[df["home_municipality"].isin(koder) & df["work_municipality"].isin(koder)]
    if df.empty:
        return None, None
    ar = None
    if "year" in df.columns and df["year"].notna().any():
        ar = int(df["year"].max())
        df = df[df["year"] == ar]
    tot = float(df["employed"].sum())
    if tot <= 0:
        return None, None
    over = float(df[df["home_municipality"] != df["work_municipality"]]["employed"].sum())
    return over / tot, ar


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
