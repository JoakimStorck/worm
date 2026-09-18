"""Kompetenscirklarna: exponering, läckage, diffusion, skärpning, q.
Se docs/individmodell.md, avsnitt 2."""
import numpy as np
import pytest

from core.occupations.competence import Circles, CompetenceParams, seed_circles, EMPTY

RO = 0.27


def _one(tenure, edu=3, p=None):
    p = p or CompetenceParams()
    c = Circles(1, 12)
    seed_circles(c, 0, "A", 0.3, 0.1, RO, tenure, edu, p)
    return c, p


def q_at(c, p, x=0.3, y=0.1, ro=RO):
    return float(c.competitiveness(0, [x], [y], [ro], p)[0])


def test_single_mature_circle_is_the_unit():
    """q = 1 är NORMERINGEN: en ensam, mogen, skärpt arbetscirkel exakt på
    jobbet. Den låg tidigare bakom ett min(1, .) som gjorde 1 till ett tak."""
    p = CompetenceParams()
    c = Circles(1, 12)
    c.add(0, "A", 0.3, 0.1, RO ** 2, p.a / p.lam * 0.99, rho2_home=RO ** 2)
    assert q_at(c, p) == pytest.approx(1.0, abs=0.02)


def test_breadth_pays_above_the_unit():
    """En mogen arbetare bär också grundskolecirkeln vid origo och en
    utbildningscirkel på yrkets riktning. Alla tre överlappar jobbet, och
    summan ÖVERSTIGER enheten: bredd betalar sig. Taket dolde det -- och
    gjorde samtidigt 41 procent av lönerna till en atom på w/Pi = 0.85,
    eftersom p = q**(k*r) blev exakt 1 för alla i taket."""
    c, p = _one(tenure=20)
    assert q_at(c, p) > 1.0
    assert q_at(c, p) < 1.3               # men inte orimligt mycket
    c1, _ = _one(tenure=20, edu=1)        # utan utbildningscirkel: mindre
    assert q_at(c1, p) < q_at(c, p)


def test_learning_curve_saturates():
    """Skillnaden noll-två år ska vara stor, tio-tjugo liten."""
    q = {t: q_at(*_one(t)) for t in (0.5, 2, 5, 10, 20)}
    assert q[0.5] < q[2] < q[5] <= q[10] <= q[20]
    assert q[2] - q[0.5] > 5 * (q[20] - q[10])


def test_forgetting_is_fast_then_slow_and_never_zero():
    """Diffusion: toppen faller som 1/(rho2 + 2Dt)."""
    c, p = _one(tenure=20)
    qs = []
    for yr in (0, 5, 10, 20, 30):
        cc, _ = _one(tenure=20)
        for _ in range(yr * 12):
            cc.evolve(1 / 12, np.array([EMPTY]), p)
        qs.append(q_at(cc, p))
    assert qs[0] > qs[1] > qs[2] > qs[3] > qs[4] > 0.05, qs
    # snabbare i början
    assert (qs[0] - qs[1]) > (qs[3] - qs[4])


def test_leakage_prevents_mass_from_defeating_diffusion():
    """REGRESSION i design: utan läckage skulle en stor massa göra diffusionen
    verkningslös -- fyrtio års snickare fullt konkurrenskraftig efter trettio
    års uppehåll."""
    p_leak = CompetenceParams()
    p_noleak = CompetenceParams(lam=1e-9)
    for p in (p_leak, p_noleak):
        cc, _ = _one(tenure=40, p=p)
        for _ in range(30 * 12):
            cc.evolve(1 / 12, np.array([EMPTY]), p)
        if p is p_leak:
            q_leak = q_at(cc, p)
        else:
            q_noleak = q_at(cc, p)
    assert q_leak < q_noleak
    assert q_leak < 0.5, "läckaget biter inte"


def test_activity_sharpens_and_accumulates():
    c, p = _one(tenure=20)
    for _ in range(10 * 12):
        c.evolve(1 / 12, np.array([EMPTY]), p)          # tio år borta
    q_rusty = q_at(c, p)
    k = c.code("A")
    for _ in range(12):
        c.evolve(1 / 12, np.array([k]), p)              # ett år tillbaka
    assert q_at(c, p) > q_rusty + 0.2, "återupptagen aktivitet skärper inte"


def test_entrant_has_low_uniform_floor():
    c, p = _one(tenure=0, edu=1)
    q_near = q_at(c, p)
    q_far = q_at(c, p, x=-0.6, y=0.0)
    assert 0.0 < q_far < 0.15 and 0.0 < q_near < 0.15
    assert abs(q_near - q_far) < 0.05, "golvet ska vara nästan likformigt"


def test_two_occupations_both_contribute_and_old_one_fades():
    p = CompetenceParams()
    c = Circles(1, 12)
    seed_circles(c, 0, "A", 0.3, 0.1, RO, 10, 3, p)
    c.add(0, "B", -0.4, 0.2, RO ** 2, 3.0, rho2_home=RO ** 2)
    qa0, qb0 = q_at(c, p), q_at(c, p, x=-0.4, y=0.2)
    assert qa0 > 0.5 and qb0 > 0.5
    kb = c.code("B")
    for _ in range(10 * 12):
        c.evolve(1 / 12, np.array([kb]), p)             # arbetar i B
    assert q_at(c, p, x=-0.4, y=0.2) > qb0
    assert q_at(c, p) < qa0, "den bortvalda cirkeln vittrar inte"
    assert q_at(c, p) > 0.05, "men den försvinner inte"


def test_full_row_grows_and_nothing_is_forgotten():
    """Inget tak (individmodell.md, avsnitt 2): en full rad växer, och den
    lättaste cirkeln ligger kvar. Tidigare föll den bort."""
    c = Circles(2, 3)
    c.add(0, "big", 0, 0, 0.1, 10.0)
    c.add(0, "small", 0.1, 0, 0.1, 0.1)
    c.add(0, "mid", 0.2, 0, 0.1, 1.0)
    c.add(0, "new", 0.3, 0, 0.1, 0.5)
    names = {c.key_names[k] for k in c.key[0] if k != EMPTY}
    assert names == {"big", "small", "mid", "new"}
    assert c.K > 3
    assert c.counts().tolist() == [4, 0]
    for arr in (c.x, c.y, c.rho2, c.rho2_home, c.mass, c.key):
        assert arr.shape == (2, c.K)
    # den nya cirkeln bär sina egna värden, inte tomvärdena
    j = int(np.flatnonzero(c.key[0] == c.key_index["new"])[0])
    assert (c.x[0, j], c.rho2[0, j], c.mass[0, j]) == (0.3, 0.1, 0.5)


def test_growth_leaves_everyone_else_unchanged():
    """De nya kolumnerna ska vara tomma i alla avseenden: den som inte
    behövde fler platser ska räknas exakt som förut, genom månadsstegen och
    i konkurrenskraften. Annars är steg 2 inte bara ett borttaget tak."""
    p = CompetenceParams(K=3)
    a, b = Circles(2, 3), Circles(2, 3)
    for c in (a, b):
        seed_circles(c, 0, "A", 0.3, 0.1, RO, 4.0, 3, p)
        seed_circles(c, 1, "B", -0.2, 0.3, RO, 6.0, 5, p)
    b.add(0, "extra", 0.5, -0.1, 0.1, 1.0)          # bara b växer
    assert b.K > a.K
    active = np.array([a.code("A"), a.code("B")])
    assert b.code("A") == active[0] and b.code("B") == active[1]
    for _ in range(24):
        a.evolve(1 / 12, np.array([EMPTY, active[1]]), p)
        b.evolve(1 / 12, np.array([EMPTY, active[1]]), p)
    jx, jy, jro = [-0.2, 0.1, 0.4], [0.3, 0.0, -0.2], [RO, 0.3, 0.2]
    assert np.array_equal(a.competitiveness(1, jx, jy, jro, p),
                          b.competitiveness(1, jx, jy, jro, p))
    assert np.array_equal(a.mass[1], b.mass[1, :a.K])
    assert np.array_equal(a.rho2[1], b.rho2[1, :a.K])
    assert (b.key[1, a.K:] == EMPTY).all() and (b.mass[:, a.K:][b.key[:, a.K:] == EMPTY] == 0).all()


def test_the_old_cap_key_is_refused():
    """max_circles var ett tak. Ett scenario som anger det väntar sig att
    cirklar faller bort och ska inte tyst få radens startbredd i stället."""
    with pytest.raises(ValueError, match="circle_slots"):
        CompetenceParams.from_config({"competence": {"max_circles": 12}})
    assert CompetenceParams.from_config({"competence": {"circle_slots": 5}}).K == 5


def test_same_key_merges_mass_weighted():
    c = Circles(1, 12)
    c.add(0, "A", 0.3, 0.1, 0.10, 1.0)
    c.add(0, "A", 0.3, 0.1, 0.30, 3.0)
    assert int((c.key[0] != EMPTY).sum()) == 1
    assert c.mass[0, 0] == pytest.approx(4.0)
    assert c.rho2[0, 0] == pytest.approx(0.25)


def test_summary_is_sane():
    p = CompetenceParams()
    c = Circles(2, 12)
    seed_circles(c, 0, "A", 0.3, 0.1, RO, 10, 3, p)
    seed_circles(c, 1, None, 0.0, 0.0, RO, 0, 1, p)      # bara grundskola
    s = c.summarize()
    assert s["x_occ"][0] == pytest.approx(0.3, abs=0.05)
    assert 0 <= s["R"][0] <= 1
    assert s["r_i"][1] > s["r_i"][0], "nybörjaren ska vara bredare"


def test_world_integration_circles_follow_career():
    """Cirklarna ska följa karriären genom motorn: tillträde aktiverar,
    månadssteg exponerar och skärper, uppsägning avaktiverar och låter
    diffusionen verka. Sammanfattningen ska spegla det."""
    import os, sys
    import pandas as pd
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from conftest import make_world
    from core.event_handlers import handle_start_job, _become_unemployed

    w = make_world(n_employers=4, size=2)
    w.individuals = pd.DataFrame([{
        "individual_id": "i0", "status": "unemployed", "job_id": None,
        "w_res": 0.5, "chi": 0.3, "xi": 0.3, "r_i": 0.0,
        "x_occ": 0.3, "y_occ": 0.1, "x": 0.0, "y": 0.0,
        "onet_code": "11-1011.00", "last_onet_code": "11-1011.00",
        "r_o_home": 0.27, "tenure_years": 3.0, "education_level": 3,
        "municipal_code": "2062", "propensity_start_education": 0.0,
        "propensity_internal_training": 0.0, "propensity_quit_job": 0.0,
        "propensity_internal_job_change": 0.0}]).astype({"job_id": object})
    w.init_competence()
    assert hasattr(w, "circles")
    assert w._active_key[0] == EMPTY

    # Ett jobb i ett ANNAT yrke, långt bort i planet
    w.jobs.loc[w.jobs.index[3], ["onet_code", "x_occ", "y_occ", "r_o"]] = ["49-9999.00", -0.5, 0.2, 0.3]
    w._ja_n = None
    jid = w.jobs.at[3, "job_id"]
    try:
        handle_start_job({"time": 1.0, "agent_id": 0, "event_type": "start_job",
                          "params": {"job_id": jid}}, w)
    except KeyError:
        pass                       # senare steg kräver full scenariokonfiguration
    assert w._active_key[0] >= 0, "tillträdet aktiverade ingen cirkel"
    assert w.individuals.at[0, "last_onet_code"] == "49-9999.00"

    p = w.competence_params()
    q_new_before = float(w.circles.competitiveness(0, [-0.5], [0.2], [0.3], p)[0])
    for _ in range(36):
        w.evolve_competence(1 / 12)
    q_new_after = float(w.circles.competitiveness(0, [-0.5], [0.2], [0.3], p)[0])
    assert q_new_after > q_new_before + 0.3, "tre års arbete byggde ingen konkurrenskraft"

    # Sammanfattningen har flyttat mot det nya jobbet
    assert w.individuals.at[0, "x_occ"] < 0.3

    _become_unemployed(w, 0, 100.0)
    assert w._active_key[0] == EMPTY
    for _ in range(120):
        w.evolve_competence(1 / 12)
    q_faded = float(w.circles.competitiveness(0, [-0.5], [0.2], [0.3], p)[0])
    assert 0.0 < q_faded < q_new_after, "diffusionen verkade inte efter uppsägning"


def test_u_R_occ_measures_from_source_occupation():
    """REGRESSION: last_onet_code skrevs över med det nya jobbets yrke innan
    u_R_occ räknades, så avståndet blev noll för varje övergång i en hel
    femårskörning."""
    import os, sys
    import pandas as pd
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from conftest import make_world
    from core.event_handlers import handle_start_job

    w = make_world(n_employers=3, size=2)
    w.individuals = pd.DataFrame([{
        "individual_id": "i0", "status": "unemployed", "job_id": None,
        "w_res": 0.5, "chi": 0.3, "xi": 0.3, "r_i": 0.0,
        "x_occ": 0.3, "y_occ": 0.1, "x": 0.0, "y": 0.0,
        "onet_code": "A", "last_onet_code": "A",
        "r_o_home": 0.27, "tenure_years": 3.0, "education_level": 3,
        "municipal_code": "2062", "propensity_start_education": 0.0,
        "propensity_internal_training": 0.0, "propensity_quit_job": 0.0,
        "propensity_internal_job_change": 0.0}]).astype({"job_id": object})
    w.init_competence()
    # Geometriuppslag utan databas: A vid (0.3, 0.1), B vid (-0.5, 0.2)
    geom = {"A": {"x_occ": 0.3, "y_occ": 0.1, "r_o": 0.27},
            "B": {"x_occ": -0.5, "y_occ": 0.2, "r_o": 0.30}}
    w._geom_lookup = lambda code: geom.get(code)
    w.jobs.loc[w.jobs.index[4], ["onet_code", "x_occ", "y_occ", "r_o"]] = ["B", -0.5, 0.2, 0.30]
    w._ja_n = None

    try:
        handle_start_job({"time": 1.0, "agent_id": 0, "event_type": "start_job",
                          "params": {"job_id": w.jobs.at[4, "job_id"]}}, w)
    except KeyError:
        pass
    logged = [e[1] for e in w.event_logger.events if e[0] == "start_job"]
    assert logged and "u_R_occ" in logged[-1]
    # d(A -> B) = hypot(0.8, 0.1) ≈ 0.806, normerat med KÄLLANS r_o = 0.27
    assert logged[-1]["u_R_occ"] == pytest.approx(0.806 / 0.27, abs=0.05)
    assert logged[-1]["from_onet"] == "A"
    assert w.individuals.at[0, "last_onet_code"] == "B"


def test_coverage_is_a_union_not_a_sum():
    """REGRESSION: summan över cirklar hade ingen gräns. Massan är bunden av
    balansen tillväxt mot glömska, m* = a/lambda = 21.6, och en ensam cirkel på
    jobbet mättar mot 1 -- men N skarpa cirklar på samma ställe gav q = N.
    Tjugo år i ett jobb gav 1.00; samma tjugo år delade på tre NÄRLIGGANDE
    YRKEN gav 2.66. Inom samma yrke slås cirklarna ihop (nyckeln är
    yrkeskoden), så fragmenteringen sker mellan grannyrken.

    Bredd lönar sig när en andra erfarenhet täcker uppgifter i jobbet som den
    första inte täckte -- och bara då. q är unionen av täckning."""
    p = CompetenceParams()

    def q_of(cirklar):
        c = Circles(1, 12)
        for n, (x, y, rho2, m) in enumerate(cirklar):
            c.add(0, f"Y{n}", x, y, rho2, m, rho2_home=RO ** 2)   # olika yrken
        return q_at(c, p, x=0.42, y=0.14, ro=RO)

    mogen = (0.42, 0.14, RO ** 2, 13.05)
    halv = (0.42, 0.14, RO ** 2, 4.35)

    ett = q_of([mogen])
    assert ett == pytest.approx(1.0, abs=0.01)
    # Två grannyrken exakt på jobbet: samma uppgifter två gånger, räknas en gång
    assert q_of([mogen, mogen]) == pytest.approx(ett, abs=0.02)
    # Fragmentering över tre grannyrken lönar sig inte: tre halva = en hel
    assert q_of([halv, halv, halv]) < 1.1
    # Men bredd som täcker olika delar av jobbet räknas
    två_sidor = q_of([(0.30, 0.14, RO ** 2, 13.05), (0.54, 0.14, RO ** 2, 13.05)])
    en_sida = q_of([(0.30, 0.14, RO ** 2, 13.05)])
    assert två_sidor > en_sida
    # och nybörjaren är oförändrad
    assert q_of([(0.0, 0.0, 1.0, 1.0)]) == pytest.approx(0.047, abs=0.005)


def _union_enligt_formeln(c, p, jx, jy, jro):
    """q = sum_k c_k * prod_{l<k} (1 - O_lk * min(c_l, 1)), cirklarna i
    fallande bidragsordning, räknad jobb för jobb och par för par. Oberoende
    av kodens vektorisering: det är formeln i docs/lonemodell.md 1.1."""
    occ = c.key[0] != EMPTY
    cx, cy, r2, m = c.x[0, occ], c.y[0, occ], c.rho2[0, occ], c.mass[0, occ]
    ut = []
    for x, y, ro in zip(jx, jy, jro):
        w = r2 + ro ** 2
        bidrag = ((1 - np.exp(-m / p.m_ref)) * (2 * ro ** 2 / w)
                  * np.exp(-0.5 * ((cx - x) ** 2 + (cy - y) ** 2) / (p.gamma ** 2 * w)))
        ordning = sorted(range(len(bidrag)), key=lambda k: -bidrag[k])
        q = 0.0
        for plats, k in enumerate(ordning):
            faktor = 1.0
            for l in ordning[:plats]:
                s2 = r2[k] + r2[l]
                O = (np.exp(-((cx[k] - cx[l]) ** 2 + (cy[k] - cy[l]) ** 2) / (2 * s2))
                     * 2 * np.sqrt(r2[k] * r2[l]) / s2)
                faktor *= 1 - O * min(bidrag[l], 1.0)
            q += bidrag[k] * faktor
        ut.append(q)
    return np.array(ut)


def test_union_follows_the_formula_for_many_circles():
    """REGRESSION: unionen drog av cirkeln på plats k bara mot den på plats
    k-1 och förde produkten vidare i en kedja -- prod_j (1 - O_{j-1,j}
    c_{j-1}) i stället för prod_{l<k} (1 - O_lk c_l). För två cirklar är det
    samma sak, därför fångade inget test det; från tre cirklar är det fel,
    och med en cirkel per händelse (docs/individmodell.md 2) är tre eller
    fler regel. Slumpade cirklar, alltså inga symmetrier som kan dölja
    ordningsfel."""
    p = CompetenceParams()
    rng = np.random.default_rng(11)
    for K in (3, 4, 6, 9):
        for _ in range(8):
            c = Circles(1, 12)
            for k in range(K):
                c.add(0, f"K{k}", float(rng.normal(0, 0.3)), float(rng.normal(0, 0.3)),
                      float(rng.uniform(0.02, 0.4)), float(rng.uniform(0.3, 15.0)))
            jx, jy = rng.normal(0, 0.3, 40), rng.normal(0, 0.3, 40)
            jro = rng.uniform(0.1, 0.35, 40)
            koden = c.competitiveness(0, jx, jy, jro, p)
            np.testing.assert_allclose(koden, _union_enligt_formeln(c, p, jx, jy, jro),
                                       rtol=0, atol=1e-12)


def test_a_circle_that_shares_nothing_with_the_stronger_counts_in_full():
    """Två identiska anställningar A och B i ett yrke, och en cirkel C åt
    andra hållet som inte överlappar dem. C ska räknas fullt: det C täcker
    täcker varken A eller B. Kedjan drog av C för A:s täckning, eftersom A
    och B överlappar varandra, och gav 0.858 mot 0.978 i ett exempel."""
    p = CompetenceParams()
    RO2 = 0.15 ** 2
    A = (0.35, 0.0, RO2, 13.0)
    C = (-0.35, 0.0, RO2, 13.0)

    def q_of(cirklar):
        c = Circles(1, 12)
        for n, t in enumerate(cirklar):
            c.add(0, f"H{n}", *t)
        return float(c.competitiveness(0, [0.05], [0.0], [0.15], p)[0])

    ensam_c = q_of([C])
    assert ensam_c > 0.05, "testet saknar tänder om C inte bidrar"
    assert q_of([A, A, C]) - q_of([A, A]) == pytest.approx(ensam_c, abs=0.002)


def test_union_is_vectorised_over_jobs():
    """REGRESSION: unionen (0078) loopade i Python ÖVER JOBBEN -- 144
    operationer per kandidat, alltså 1.5 miljoner per sökning med tiotusen
    lediga jobb. Uppstarten, som söker mot hela jobbstocken, blev praktiskt
    taget stillastående: 67 ms per anrop mot 1.8 vektoriserat, trettiosju
    gånger. Ordningen skiljer sig per jobb, vilket tvingade fram loopen;
    take_along_axis löser det och kvar blir en loop över de tolv cirklarna."""
    import inspect
    import numpy as np
    from core.occupations import competence as C

    kod = [ln for ln in inspect.getsource(C.Circles._union).splitlines()
           if not ln.lstrip().startswith("#")]
    text = "".join("\n".join(kod).split('"""')[::2])
    assert "for j in range(J)" not in text, "loopar över jobben igen"
    assert "take_along_axis" in text

    # Och utfallet är detsamma för många jobb som för ett
    p = CompetenceParams()
    c = Circles(1, 12)
    for n, (x, y, rho2, m) in enumerate([(0.42, 0.14, RO ** 2, 13.05),
                                         (0.30, 0.14, RO ** 2, 8.0),
                                         (0.0, 0.0, 1.0, 1.0)]):
        c.add(0, f"Y{n}", x, y, rho2, m, rho2_home=RO ** 2)
    rng = np.random.default_rng(0)
    jx, jy = rng.uniform(-0.4, 0.4, 50), rng.uniform(-0.4, 0.4, 50)
    jr = np.full(50, RO)
    många = c.competitiveness(0, jx, jy, jr, p)
    for i in range(50):
        ett = c.competitiveness(0, jx[i:i + 1], jy[i:i + 1], jr[i:i + 1], p)[0]
        assert många[i] == pytest.approx(ett, rel=1e-12)


def test_circle_counts_reach_the_log_and_the_run_table(tmp_path):
    """Hela vägen: årsskiftet mäter cirklarna, den riktiga loggen skriver
    dem, läsaren tolkar raden och körningstabellen bär dem. Slutläget får
    dem som kolumner i individtabellen. Stock-fälten tappades en gång på
    just den vägen (se test_stock_and_revision_reach_the_run_table)."""
    import os, sys
    import pandas as pd
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from conftest import make_world
    from core.event_handlers import handle_new_year
    from core.log import EventLogger
    from core.analysis.eventlog import parse_line, summary_row

    w = make_world(n_employers=2, size=1)
    w.individuals = pd.DataFrame([{
        "individual_id": f"i{k}", "status": "unemployed", "job_id": None,
        "w_res": 0.5, "chi": 0.3, "xi": 0.3, "r_i": 0.0,
        "x_occ": 0.3, "y_occ": 0.1, "x": 0.0, "y": 0.0,
        "onet_code": "11-1011.00", "r_o_home": 0.27, "tenure_years": 3.0,
        "education_level": 3, "municipal_code": "2062"} for k in range(2)]
    ).astype({"job_id": object})
    w.init_competence()
    # individ 0 får fler yrken än startbredden rymmer; individ 1 har
    # startens tre
    for k in range(12):
        w.circles.add(0, f"yrke{k}", 0.1, 0.1, 0.1, 0.01 * (k + 1))
    assert w.circles.counts().tolist() == [15, 3]

    path = tmp_path / "eventlog.csv"
    w.event_logger = EventLogger(str(path))
    handle_new_year({"time": 0.0, "agent_id": None, "event_type": "new_year",
                     "params": {"year": 2024}}, w)
    w.event_logger.close()
    ev = [r for r in (parse_line(l) for l in path.read_text(encoding="utf-8").splitlines())
          if r is not None and r.get("event") == "new_year"]
    assert len(ev) == 1
    rad = ev[0]
    assert int(rad["circles_max"]) == 15
    assert int(rad["circles_over_12"]) == 1
    assert int(rad["circles_width"]) == w.circles.K >= 15
    assert float(rad["circles_mean"]) == pytest.approx((15 + 3) / 2)

    tr = pd.DataFrame({"u_R": [0.7], "u_R_occ": [0.7], "w_neg": [1.0],
                       "w_occ": [1.0], "w_field": [1.0], "wage_ratio": [1.0],
                       "in_cps_sample": [True], "occ_change": [True],
                       "is_mgmt": [False], "r_req": [0.3], "q_hire": [0.9],
                       "commute_km": [5.0], "n_applicants": [3.0]})
    ts = pd.DataFrame({"year": [1.0], "month": [1], "vacancies": [10],
                       "employed": [90], "unemployed": [10],
                       "labour_force": [100], "active_jobs": [100],
                       "posted": [0], "not_in_labour_force": [0],
                       "u": [10.0], "v": [10.0], "tightness": [1.0],
                       "identity_residual": [0]})
    row = summary_row(str(tmp_path), events=ev, tr=tr, ts=ts)
    assert row["circles_max"] == 15
    assert row["circles_width"] == w.circles.K

    w._write_competence_summary()
    assert w.individuals["n_circles"].tolist() == [15, 3]
