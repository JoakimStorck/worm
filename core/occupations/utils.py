# core/occupations/utils.py
# Euklidisk matchning i den task-baserade geometrin (x_occ, y_occ), kärnbredd = r_o.

import pandas as pd
import numpy as np
import math
from scipy.optimize import linear_sum_assignment


def select_representative_occupations(df):
    representatives = []
    for cluster_id in df['cluster'].unique():
        cluster_df = df[df['cluster'] == cluster_id]
        centroid = cluster_df[['pc1', 'pc2']].mean().values
        distances = ((cluster_df[['pc1', 'pc2']].values - centroid) ** 2).sum(axis=1)
        best_idx = distances.argmin()
        representatives.append(cluster_df.iloc[best_idx])
    return pd.DataFrame(representatives)


def name_clusters_by_representative_titles(df):
    names = {}
    for _, row in df.iterrows():
        short_title = row['title'].split(',')[0].split('(')[0].strip()
        names[row['cluster']] = f"{short_title} ({row['cluster']})"
    return names


def reorder_clusters_by_angle(df):
    centroids = df.groupby('cluster')[['chi', 'xi']].mean()
    sorted_clusters = centroids.sort_values('xi').index.tolist()
    mapping = {old: new for new, old in enumerate(sorted_clusters)}
    df['cluster'] = df['cluster'].map(mapping)
    return df


# ---------------------------------------------------------------------------
# Matchning: euklidiskt avstånd i (x_occ, y_occ), gaussisk kärna med bredd r_o.
# sigma^2 = H_individ^2 + r_o_jobb^2  (faltning: arbetartolerans + yrkesräckvidd)
# alpha_chi/alpha_xi behålls i signaturen för bakåtkompatibilitet men används ej.
# ---------------------------------------------------------------------------
def _occ_distance(inds_df, jobs_df):
    ix = inds_df["x_occ"].values[:, None]; iy = inds_df["y_occ"].values[:, None]
    jx = jobs_df["x_occ"].values[None, :]; jy = jobs_df["y_occ"].values[None, :]
    return np.sqrt((ix - jx) ** 2 + (iy - jy) ** 2)          # (n_ind, n_jobs)


def _occ_prob(inds_df, jobs_df, occ_dist, sigma_gamma=1.0):
    """Matchproduktivitet som gaussisk kärna i planet.

    Bredden är GEOMETRISK: yrkets task-radie r_o (Ekv. 2) faltad med arbetarens
    erfarenhetsradie r_i (spridningen i det egna yrkeshistoriken). Bägge är RMS-
    avstånd i samma plan och därmed kommensurabla med occ_dist.

        sigma = sigma_gamma * sqrt(r_o^2 + r_i^2)

    r_i saknas eller = 0 ger sigma = sigma_gamma * r_o, vilket är formuleringen
    i pappret och i GTS-motorn (dar bredden sitter helt pa yrket/familjen).
    sigma_gamma < 1 skarper matchningen; den ar avsedd som kalibreringsratt mot
    en malvakansgrad.
    """
    ro = jobs_df["r_o"].values[None, :]
    if "r_i" in inds_df.columns:
        ri = np.nan_to_num(inds_df["r_i"].values)[:, None]
    else:
        ri = 0.0
    sigma2 = np.maximum((sigma_gamma ** 2) * (ro ** 2 + ri ** 2), 1e-9)
    return np.exp(-0.5 * occ_dist ** 2 / sigma2)


def _geo_km(inds_df, jobs_df):
    dx = inds_df["x"].values[:, None] - jobs_df["x"].values[None, :]
    dy = inds_df["y"].values[:, None] - jobs_df["y"].values[None, :]
    return np.sqrt(dx ** 2 + dy ** 2) / 1000.0


def compute_utility_matrix(individuals_df, jobs_df,
                           alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0,
                           sigma_gamma=1.0, commute_cost_per_km=0.005):
    """Bakåtkompatibelt namn. Returnerar överskottsmatrisen."""
    return compute_surplus_matrix(individuals_df, jobs_df,
                                  sigma_gamma=sigma_gamma,
                                  commute_cost_per_km=commute_cost_per_km)


def chi_add(chi, delta):
    return min(max(chi + delta, 0.0), 1.0)

def r_add(r_i, delta):
    """Justerar erfarenhetsradien (bredd i planet)."""
    return min(max(r_i + delta, 0.0), 1.0)


# Bakåtkompatibelt alias (H hette tidigare kompetensbredd/entropi)
H_add = r_add

def xi_add(xi, delta):
    return (xi + delta) % (2 * np.pi)


def sample_centers_xy_jitter(x_vals, y_vals, weights, n_samples, sigma_xy, power=1.5):
    """Välj yrkescentrum efter vikt och lägg kartesisk gaussisk jitter; klipp till enhetsskivan."""
    w = np.asarray(weights, dtype=float)
    w = (w ** power); w = w / w.sum()
    idx = np.random.choice(len(x_vals), size=n_samples, p=w)
    x = x_vals[idx] + np.random.normal(0, sigma_xy, size=n_samples)
    y = y_vals[idx] + np.random.normal(0, sigma_xy, size=n_samples)
    r = np.hypot(x, y)
    over = r > 1.0
    x[over] /= r[over]; y[over] /= r[over]      # projicera in i skivan
    return x, y


def sample_from_centers_jitter(xi_vals, chi_vals, weights, n_samples, sigma_xi, sigma_chi):
    """Bevarad polär sampler (bakåtkompatibilitet)."""
    w = np.asarray(weights, dtype=float)
    w = (w ** 1.5); w = w / w.sum()
    idx = np.random.choice(len(xi_vals), size=n_samples, p=w)
    xi = (xi_vals[idx] + np.random.normal(0, sigma_xi, size=n_samples)) % (2 * np.pi)
    chi = np.clip(chi_vals[idx] + np.random.normal(0, sigma_chi, size=n_samples), 0, 1)
    return xi, chi


def apply_capability_update_LEGACY(chi, xi, r_i, delta_chi=0.0, delta_xi=0.0, delta_r=0.0,
                            switch_cost_kappa=0.0, breadth_from_move=0.25):
    """
    Uppdaterar (chi, xi, r_i) i enhetsskivan och returnerar synkade (x_occ, y_occ).

    Tva geometriska mekanismer:

    1. BYTARKOSTNAD. Vinkelforflyttning drar av djup (chi) proportionellt mot
       kortaste vinkelavstandet: riktningsbyte urholkar riktningsspecifikt
       humankapital (Gathmann-Schonberg; storre vinkelgap <-> storre
       kapabilitetsskillnad).

    2. BREDDNING. Erfarenhetsradien r_i vaxer med den faktiska forflyttningen i
       planet, som ett lopande RMS: r_i' = sqrt(r_i^2 + breadth_from_move * d^2).
       En arbetare som rort sig langt mellan yrken tacker ett bredare omrade;
       en som stannat kvar forblir en punkt. Det ersatter den tidigare
       entropin H, som lag pa en skala som inte var kommensurabel med planet.

    Returnerar (chi, xi, r_i, x_occ, y_occ).
    """
    chi, xi, r_i = float(chi), float(xi), float(r_i)
    x0, y0 = chi * np.cos(xi), chi * np.sin(xi)

    ang = abs((float(delta_xi) + np.pi) % (2 * np.pi) - np.pi)      # kortaste vinkel
    xi_new = (xi + float(delta_xi)) % (2 * np.pi)
    chi_new = min(max(chi + float(delta_chi) - switch_cost_kappa * ang, 0.0), 1.0)
    x1, y1 = chi_new * np.cos(xi_new), chi_new * np.sin(xi_new)

    moved = float(np.hypot(x1 - x0, y1 - y0))
    r_new = np.sqrt(max(r_i ** 2 + breadth_from_move * moved ** 2, 0.0))
    r_new = min(max(r_new + float(delta_r), 0.0), 1.0)
    return chi_new, xi_new, r_new, x1, y1


# ---------------------------------------------------------------------------
# Jobbsökning: relevansmängd och logit-val
# ---------------------------------------------------------------------------
JOB_ARRAY_COLS = ("x_occ", "y_occ", "r_o", "wage", "x", "y", "r_req")


def build_job_arrays(jobs_df):
    """Numpy-vy av jobbtabellen. Beräkning på arrayer i stället för på
    DataFrame-utsnitt: mätt tar full beräkning över 1500 vakanser 47 mikro-
    sekunder, medan enbart jobs.iloc[400] tar 116. Kostnaden låg i
    DataFrame-konstruktionen, inte i aritmetiken."""
    out = {}
    for c in JOB_ARRAY_COLS:
        out[c] = (jobs_df[c].to_numpy(dtype=float) if c in jobs_df.columns
                  else np.zeros(len(jobs_df)))
    if "wage" not in jobs_df.columns:
        out["wage"] = np.ones(len(jobs_df))
    if "r_req" not in jobs_df.columns:
        # Ingen kravmodell alls (minimala ramar i test): jobbet ställer inga
        # särskilda krav, p = q**0 = 1. Fallbacken var tidigare r = 1, det
        # STRÄNGASTE tänkbara kravet, vilket gör varje jobb till ett kirurgjobb
        # med grinden q >= sqrt(phi) = 0.837. En okänd storhet ska inte gissas
        # åt det håll som gör mest skada.
        out["r_req"] = np.zeros(len(jobs_df))
    elif not np.isfinite(out["r_req"]).all():
        # Kolumnen finns men är delvis tom. Kravintensiteten kommer ur ett
        # analytiskt fält som täcker varje position, så NaN betyder att
        # kapabilitetsfältet saknas eller att geometrin är inkonsekvent. Då
        # ska körningen stanna: både 0 och 1 ger tysta, motsatta fel.
        n_bad = int((~np.isfinite(out["r_req"])).sum())
        raise ValueError(
            f"r_req saknas för {n_bad} av {len(jobs_df)} jobb. Kravintensiteten "
            "kommer ur data/geometry/capability_field_coefficients.csv via "
            "scripts/load_task_geometry.py; kör om inläsningen.")
    return out


def vacant_job_indices(jobs_df):
    """Positionsindex för lediga, aktiva positioner. Ingen kopia av ramen."""
    vac = jobs_df["individual_id"].isna().to_numpy(copy=True)
    if "active" in jobs_df.columns:
        vac &= jobs_df["active"].to_numpy(dtype=bool)
    return np.flatnonzero(vac)


def search_once(ind, jobs_df, cand_idx, queue=None, sigma_gamma=1.0,
                commute_cost_per_km=0.005, min_surplus=0.0,
                choice_scale=0.05, rng=None, arrays=None,
                competitiveness=None, bargaining=None, requirement_k=2.0):
    """En sökomgång. Två steg, i linje med hur jobbsökning faktiskt går till.

    1. RELEVANSMÄNGD. Den sökande överväger de positioner hon rimligen kan
       få och utföra. Sannolikheten att en position är ett levande alternativ
       är p = exp(-d^2 / 2 sigma^2) i uppgiftsrummet. p bär både relevans och
       arbetsgivarens vilja att anställa; att dela upp dem i två gaussiska
       filter vore observationellt ekvivalent men skulle kräva att sigma
       kalibrerades om med faktorn sqrt(2), utan att tillföra något.

       Mängden är INTE begränsad till ett fast antal. En arbetare i en gles
       kommun ska se färre alternativ än en i en tät -- annars kan modellen
       inte uttrycka uppgiftsrummets tunnhet.

    2. VALET. Bland de alternativ som ger positivt överskott väljs ett med
       logit-sannolikhet proportionell mot exp(S / choice_scale), där
       S = w - c*km - w_res. Eftersom pendlingskostnaden ligger i S väljs ett
       närmare jobb framför ett längre bort när lönen är ungefär densamma,
       men valet är inte deterministiskt: nära likvärdiga alternativ får nära
       lika sannolikhet. choice_scale är den lönemarginal, i andelar av
       medellönen, inom vilken alternativ uppfattas som likvärdiga.

    Avståndsfördelningen blir Rayleigh med skala sigma, eftersom endast p
    beror på avståndet i planet: therefore median 1.1774*sigma, vilket är den
    empiriskt kalibrerade formen.

    Returnerar (job_index, surplus, w_off, q, km) eller (None,)*5. km är
    pendlingsavstandet till det valda jobbet: det beraknas har anda, och
    utan att returneras kan ingen efterat se hur langt nagon pendlar. Med
    flera kommuner i scenariot ar det matt som avgor om pendlingen ar
    selektiv -- om lakaren pendlar men inte diskaren -- och det ar ocksa
    den enda kalibreringen av commute_cost_per_km mot tabellen commuting.
    """
    rng = rng if rng is not None else np.random
    if cand_idx.size == 0:
        return None, None, None, None, None
    A = arrays if arrays is not None else build_job_arrays(jobs_df)

    ix = float(ind["x_occ"]); iy = float(ind["y_occ"])
    ri = float(ind.get("r_i", 0.0) or 0.0)
    gx = float(ind["x"]); gy = float(ind["y"])
    w_res = float(ind.get("w_res", 0.0) or 0.0)

    jx = A["x_occ"][cand_idx]; jy = A["y_occ"][cand_idx]
    if competitiveness is not None:
        # Konkurrenskraft q ur kompetenscirklarna (docs/individmodell.md, avsnitt 2).
        q = competitiveness(jx, jy, A["r_o"][cand_idx])
    else:
        d2 = (jx - ix) ** 2 + (jy - iy) ** 2
        sigma2 = np.maximum((sigma_gamma ** 2) * (A["r_o"][cand_idx] ** 2 + ri ** 2), 1e-9)
        q = np.exp(-0.5 * d2 / sigma2)
    # Två roller för passformen. q styr OM mötet leder någonstans -- arbets-
    # givaren föredrar den erfarna diskaren fast vem som helst kan diska, och
    # arbetaren söker sig till det hon känner till. Det är vad Rayleigh-
    # kalibreringen mot 0.70 task-radier bygger på. PRODUKTIVITETEN
    # p = q ** (k * r_req) styr vad hon är värd: lön och arbetsgivarens
    # deltagande. Att låta p styra mötet tog bort lokaliteten för halva
    # marknaden och gav median u_R 1.20.
    from core.occupations.requirement import productivity
    p = productivity(q, A["r_req"][cand_idx], k=requirement_k)

    km = np.hypot(A["x"][cand_idx] - gx, A["y"][cand_idx] - gy) / 1000.0
    w_field = A["wage"][cand_idx]
    if bargaining is not None:
        w_off = negotiated_wage(p, w_field, w_res, **bargaining)
    else:
        w_off = w_field
    S = np.where(np.isnan(w_off), -np.inf, w_off - commute_cost_per_km * km - w_res)

    # KÖN I ÖVERSKOTTET. Ett jobb med n liggande ansökningar ger henne
    # platsen med ungefär 1/(n+1), så det den är värt att söka är S/(n+1) --
    # forvantat utfall, inte annonserat. Utan detta valde logiten på
    # annonserad lön allena, och med choice_scale 0.05 mot ett lönespann
    # 0.49-1.81 blir valet nästan deterministiskt: 806 ansökningar hamnade på
    # ETT jobb, tio procent av jobben tog 73 procent av ansökningarna, och
    # 9 099 av 15 554 positioner sågs aldrig av någon under fem år. Det är
    # riktad sökning i Moens mening, och den kostar ingen ny parameter.
    if queue is not None:
        S = S / (1.0 + np.asarray(queue, float)[cand_idx])

    # Mötesdraget är en sannolikhet och kapar q själv. Värderollen (p, lön,
    # urval) använder det okapade q: taket där gjorde Pi till ett supremum.
    live = (S > min_surplus) & (rng.random(S.size) < np.minimum(1.0, q))
    if not live.any():
        return None, None, None, None, None

    k = np.flatnonzero(live)
    Sk = S[k]
    if choice_scale and choice_scale > 0:
        z = (Sk - Sk.max()) / float(choice_scale)      # stabiliserad softmax
        w = np.exp(z)
        pick = k[int(rng.choice(w.size, p=w / w.sum()))]
    else:
        pick = k[int(np.argmax(Sk))]
    return (int(cand_idx[pick]), float(S[pick]), float(w_off[pick]),
            float(q[pick]), float(km[pick]))


def retraining_target(ind, jobs_df, cand_idx, arrays=None,
                      commute_cost_per_km=0.005, min_surplus=0.0, top_k=50):
    """Målpunkt för omskolning: överskottsviktad tyngdpunkt av de nåbara
    vakanserna.

    Utbildning var tidigare en slumpvandring -- ett fast delta_xi roterade alla
    åt samma håll oavsett var jobben fanns. Då kan omskolning inte fungera som
    anpassningskanal, och modellen kan inte uttrycka att tunna marknader är
    svårare att ställa om i.

    Riktningen bestäms nu av var arbete faktiskt finns inom rimligt
    pendlingsavstånd. I en tät kommun ligger tyngdpunkten nära och
    omskolningen blir kort; i en gles ligger den långt bort, eller saknas helt,
    och då sker ingen omskolning -- vilket i sig är resultatet.

    Vikten är överskottet w - c*km (utan reservationslön: målet är vart det
    lönar sig att gå, inte vad som är godtagbart i dag). Endast de top_k bästa
    används, så att enstaka avlägsna positioner inte drar tyngdpunkten.

    Returnerar (x, y) eller None om inget rimligt mål finns.
    """
    if cand_idx.size == 0:
        return None
    A = arrays if arrays is not None else build_job_arrays(jobs_df)
    gx = float(ind["x"]) if "x" in ind.index else 0.0
    gy = float(ind["y"]) if "y" in ind.index else 0.0
    km = np.hypot(A["x"][cand_idx] - gx, A["y"][cand_idx] - gy) / 1000.0
    val = A["wage"][cand_idx] - commute_cost_per_km * km
    ok = val > min_surplus
    if not ok.any():
        return None
    idx = cand_idx[ok]
    val = val[ok]
    if idx.size > top_k:
        keep = np.argpartition(-val, top_k)[:top_k]
        idx, val = idx[keep], val[keep]
    w = val / val.sum()
    return float((w * A["x_occ"][idx]).sum()), float((w * A["y_occ"][idx]).sum())


# ---------------------------------------------------------------------------
# Förhandlad lön (docs/individmodell.md, avsnitt 5)
# ---------------------------------------------------------------------------
def negotiated_wage(p, w_field, w_res, beta=0.5, wage_floor_share=0.0,
                    theta=None, labour_share=0.65, **_ignored):
    """Lönen som avvikelse från normen, inte som delning av ett överskott.

        w = Pi * p**theta,   nedåt begränsad av avtalslönen phi*Pi
        affär om   p*Pi/lambda >= w

    THETA är graden av individuell lönesättning. theta = 0 ger alla exakt Pi
    (solidarisk lönesättning), theta = 1 ger var och en sin produktivitet. Det
    är den dimension som skiljer svenska avtalsområden åt och är därmed
    observerbar per bransch, inte en fri parameter. I logaritmer är formeln
    additiv, log w = log Pi + theta*log p, så spridningen inom yrke blir
    theta*k*r_j*sigma_log_q -- den VÄXER med kravnivån, vilket kan prövas mot
    SCB:s percentiler per SSYK utan att någon form antas.

    VARFÖR DEN GAMLA. w = (1-beta)*max(w_res, phi*Pi) + beta*p*Pi såg ut att ha
    två frihetsgrader men hade en. Reservationen faller trettio procent vid
    varje separation, så efter första arbetslöshetsperioden ligger den under
    golvet för alla, max() väljer alltid phi*Pi, och första termen är
    KONSTANT 0.5*0.70 = 0.35. Kvar blev w/Pi = 0.35 + 0.5p, och med median
    p = 0.995 satt medianen låst vid 0.8499 -- 87.5 procent av
    anställningarna följde den identiteten på tre decimaler. Pi kunde inte
    vara det Pi utger sig för att vara: ett yrkes observerade lön som hälften
    ligger över.

    Avtalslönen blir nu ett GOLV och inte halva formeln. Ett golv som bär
    trettiofem procent av lönen för var och en är inget golv.

    LOENEANDELEN. Utan lambda vore arbetsgivarens villkor p*Pi >= Pi*p**theta,
    alltså p >= 1: ingen under medianen skulle anställas. Pi är lön, inte
    produktionsvärde; värdet per arbetare är Pi/lambda. Med lambda = 0.65 och
    theta = 0.5 blir grinden p >= lambda**(1/(1-theta)) = 0.42, mot 0.70 i den
    gamla modellen. Den föll ut i 0050 därför att ankaret sattes punktvis med
    fast beta, inte för att den var överflödig.

    Reservationen står inte längre i formeln. Den avgör om hon TACKAR JA
    (S = w - c*km - w_res i search_once), inte vad hon är värd. Att lönenivån
    berodde på hur länge hon varit arbetslös var en egenskap ingen bett om.

    beta behålls för bakåtkompatibilitet: utan theta används den gamla
    formeln, så äldre scenarier ger samma utfall.

    p är PRODUKTIVITET, q ** (k * r_req). Vektoriserat; NaN utan affär.
    """
    p = np.asarray(p, dtype=float); w_field = np.asarray(w_field, dtype=float)
    if theta is None:
        value = p * w_field
        eff = np.maximum(w_res, float(wage_floor_share) * w_field) if wage_floor_share else \
            np.full_like(value, float(w_res))
        w = (1.0 - beta) * eff + beta * value
        return np.where(value >= eff, w, np.nan)

    lam = float(labour_share)
    w = w_field * np.power(np.maximum(p, 0.0), float(theta))
    if wage_floor_share:
        w = np.maximum(w, float(wage_floor_share) * w_field)
    value = p * w_field / lam                      # produktionsvärde per arbetare
    return np.where(value >= w, w, np.nan)

