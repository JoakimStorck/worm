"""
export_viz.py  (scripts/)
-------------------------
Skriver en körning till EN JSON-fil som en fristående visningsapp läser.

Visningen är frikopplad från simuleringen. Den kör inte modellen, den spelar
upp en körning som redan gjorts. Det gör demon deterministisk -- samma körning
varje gång, ingen krasch mitt i en dragning -- och gör att två körningar kan
ställas bredvid varandra.

MÅNADSTILLSTÅNDET FINNS INTE PÅ DISK. scenario_runner sparar bara
initial_state_* och final_state_*; däremellan finns bara eventloggen. Tillstånd
per månad rekonstrueras därför här, genom att spela upp loggen mot
starttillståndet:

    start_job                       individ -> jobb, jobbet besatt
    destroy_job/holder_displaced    individ -> arbetslös, jobbet inaktivt
    destroy_job/vacancy_destroyed   jobbet inaktivt
    open_advert / close_vacancy     vakansens annonstillstånd

Alternativet -- att dumpa tillståndet varje månad i simuleringen -- hade krävt
ändringar i den varma slingan och gjort alla befintliga körningar oanvändbara.
Uppspelningen fungerar på varje körning som redan ligger i output/.

Aggregaten (u, v, stockar) LÄSES ur new_month-raderna via
core/analysis/eventlog.py och räknas inte om här. Två tal för samma sak som
räknats på två ställen kommer förr eller senare att skilja sig, och då är det
figuren i en presentation som säger emot tabellen i artikeln.

Individerna urvalsbegränsas till en panel (--panel, förval 2000) som följs genom
hela körningen. Aggregaten gäller ändå hela populationen. Skälet är storlek: tre
kommuner i 120 månader är i storleksordningen 30 000 individer per bildruta, och
det är inte något en webbläsare läser in i ett stycke.

    python scripts/export_viz.py                         # senaste körningen
    python scripts/export_viz.py output/run_A --out viz/a.json
    python scripts/export_viz.py output/run_A --panel 4000 --db data/worm.sqlite3
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.analysis.eventlog import read_events, timeseries_table  # noqa: E402

SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Hjälpare
# ---------------------------------------------------------------------------
def _senaste_korning(outdir="output"):
    kandidater = [os.path.join(outdir, d) for d in sorted(os.listdir(outdir))
                  if os.path.isfile(os.path.join(outdir, d, "eventlog.csv"))]
    if not kandidater:
        raise SystemExit("Ingen körning med eventlog.csv under output/.")
    return kandidater[-1]


def _hemkommun(individual_id, fallback=None):
    """Kommunen ur individ-id:t, samma konvention som event_handlers 0105."""
    s = str(individual_id)
    if "_i" in s:
        return s.split("_i", 1)[0]
    return fallback


def _kolumn(df, *namn, default=np.nan):
    """Första kolumnen som finns, annars en konstant. Tabellerna har vuxit
    olika i olika versioner och en saknad kolumn ska inte stoppa exporten."""
    for n in namn:
        if n in df.columns:
            return df[n]
    return pd.Series([default] * len(df), index=df.index)


def _tal(v, dec=3):
    """Ett enskilt tal till JSON, avrundat, med None för det som inte är ett tal."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(f):
        return None
    return round(f, dec)


def _rund(serie, dec):
    """Avrundat till JSON. Koordinater i meter behöver inga decimaler alls, och
    full float64 fyrdubblar filen utan att synas på skärmen."""
    a = pd.to_numeric(serie, errors="coerce").to_numpy(dtype=float)
    a = np.round(a, dec)
    return [None if not np.isfinite(v) else (int(v) if dec <= 0 else float(v))
            for v in a]


# ---------------------------------------------------------------------------
# Geometri: kommunpolygoner och SCB:s pendlingsmatris ur databasen
# ---------------------------------------------------------------------------
def kommunpolygoner(db_path, koder, tolerans=200.0):
    """Kommunernas ytterkontur som GeoJSON, förenklad.

    Går genom GeoWorld och inte genom en egen SQL-fråga. Lagret har redan en
    läsare som sätter CRS (EPSG:3006) och gissar kolumnnamn; en andra läsare
    här skulle vara ett andra ställe att rätta den dagen schemat ändras.
    Saknas databasen eller geopandas returneras tom lista -- kartan ritas då
    på punktmolnet.
    """
    if not db_path or not os.path.isfile(db_path):
        return []
    try:
        from shapely.geometry import mapping

        from core.geography.geoworld import GeoWorld
    except ImportError:
        return []
    try:
        gdf = GeoWorld(db_path).municipalities
    except Exception:
        return []
    ut = []
    for _, rad in gdf.iterrows():
        kod = str(rad.get("municipal_code", ""))
        if koder and kod not in koder:
            continue
        try:
            g = rad["geometry"].simplify(tolerans, preserve_topology=True)
        except Exception:
            continue
        ut.append({"code": kod,
                   "name": str(rad.get("municipality", kod)),
                   "geometry": mapping(g)})
    return ut


def desopolygoner(db_path, koder, tolerans=150.0):
    """DeSO-områdena inom körningens kommuner.

    Bakgrundsindelning, inte gräns: DeSO är den nivå individer och
    arbetsgivare placeras på i scenariobuilder, så konturerna visar var
    modellens geografi faktiskt har sin upplösning. De ritas svagare än
    kommungränserna, som är de gränser pendlingen korsar och därmed de enda
    som bär en fråga.

    Tolerensen är tätare än kommunernas: ett DeSO i Mora tätort är litet nog
    att 200 meter suddar formen.
    """
    if not db_path or not os.path.isfile(db_path):
        return []
    try:
        from shapely.geometry import mapping

        from core.geography.geoworld import GeoWorld
    except ImportError:
        return []
    try:
        gdf = GeoWorld(db_path).deso_zones
    except Exception:
        return []
    ut = []
    for _, rad in gdf.iterrows():
        kod = str(rad.get("municipal_code", ""))
        if koder and kod not in koder:
            continue
        try:
            g = rad["geometry"].simplify(tolerans, preserve_topology=True)
        except Exception:
            continue
        ut.append({"code": str(rad.get("deso_code", "")), "mun": kod,
                   "geometry": mapping(g)})
    return ut


def yrkesrummet(db_path):
    """Yrkesrummet: varje O*NET-yrke på sin plats i det polära rummet.

    Det här är BAKGRUNDEN uppgiftsrumspanelen ritas mot. Utan den hänger en
    kompetenscirkel i tomma intet och går bara att jämföra med de jobb som
    råkar finnas i körningen; med den syns vilken del av yrkesrummet cirkeln
    täcker, vilket är det tunnhet betyder.

    Job Family är den etikett en publik kan läsa. Den gör att panelen kan
    säga vård, tillverkning eller transport i stället för att kräva att någon
    förstår vad chi och xi är, och det är skillnaden mellan en figur som
    övertygar en kommunpolitiker och en som ser ut som forskning.

    Samma tabell som scenariobuilder läser (onet_occupation_space), så
    rummet i figuren är rummet modellen räknat i.
    """
    if not db_path or not os.path.isfile(db_path):
        return {}
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM onet_occupation_space", conn)
        conn.close()
    except Exception:
        return {}
    if df.empty or "chi" not in df.columns:
        return {}
    titel = _kolumn(df, "Title", "title", default="")
    familj = _kolumn(df, "Job Family", "cluster_name", default="")
    return {
        "onet": [str(c) for c in _kolumn(df, "onet_code", default="")],
        "xi": _rund(_kolumn(df, "xi"), 4),
        "chi": _rund(_kolumn(df, "chi"), 4),
        "r_o": _rund(_kolumn(df, "r_o"), 4),
        "r_req": _rund(_kolumn(df, "r_req"), 4),
        "title": [str(t) for t in titel],
        "family": [str(f) for f in familj],
    }


def yrken_per_kommun(jobb):
    """Antal positioner per kommun och yrke, ur körningens egna jobb.

    Tunnhet är inte en egenskap hos yrkesrummet utan hos rummet SOM FINNS PÅ
    PLATSEN. Samma kompetenscirkel täcker olika många yrken i Mora och i
    Orsa, och det är den jämförelsen panelen ska kunna göra utan att räkna om
    något i webbläsaren.
    """
    if "municipal_code" not in jobb.columns or "onet_code" not in jobb.columns:
        return {}
    ut = {}
    for (kom, onet), n in jobb.groupby(
            [jobb["municipal_code"].astype(str),
             jobb["onet_code"].astype(str)]).size().items():
        ut.setdefault(kom, {})[onet] = int(n)
    return ut


def scb_pendling(db_path, koder):
    """SCB:s observerade flöden mellan kommunerna, ur tabellen `commuting`.

    Modellens pendling ska ställas mot den, inte visas ensam. Det är samma
    tabell commute_cost_per_km kalibreras mot (se core/occupations/utils.py),
    så figuren och kalibreringen läser samma tal.
    """
    if not db_path or not os.path.isfile(db_path):
        return {}
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM commuting", conn)
        conn.close()
    except Exception:
        return {}
    if not {"home_municipality", "work_municipality", "employed"} <= set(df.columns):
        return {}
    if "year" in df.columns and df["year"].notna().any():
        df = df[df["year"] == df["year"].max()]
    ut = {}
    for _, r in df.iterrows():
        h, a = str(r["home_municipality"]), str(r["work_municipality"])
        if koder and (h not in koder or a not in koder):
            continue
        ut[f"{h}>{a}"] = int(r["employed"])
    return ut


# ---------------------------------------------------------------------------
# Uppspelning
# ---------------------------------------------------------------------------
class Tillstand:
    """Individernas och jobbens tillstånd, framskrivet händelse för händelse.

    Bara det som ändras skrivs: yrkesläget (chi, xi, r_i) läses ur loggraden
    när den bär det, eftersom build_standard_logdict skriver de tre fälten för
    varje individhändelse. Utbildning och intern rörlighet flyttar därför
    individen i uppgiftsrummet utan att simuleringen behöver logga något nytt.
    """

    def __init__(self, individer, jobb):
        self.ind_jobb = {}          # individual_id -> job_id eller None
        self.ind_geom = {}          # individual_id -> (xi, chi, r)
        self.jobb_innehavare = {}   # job_id -> individual_id eller None
        self.jobb_aktivt = {}       # job_id -> bool
        self.jobb_annonserat = {}   # job_id -> bool

        for iid, jid in zip(individer["individual_id"], _kolumn(individer, "job_id")):
            self.ind_jobb[str(iid)] = None if pd.isna(jid) else str(jid)
        # UTANFÖR ARBETSKRAFTEN. Individtabellen är hela befolkningen, inte
        # arbetskraften: scenariobuilder sätter status not_in_labor_force på
        # den andel som workforce_ratio lämnar utanför. De söker aldrig och
        # förekommer aldrig i en händelse. Räknas de som arbetslösa -- vilket
        # "har inget jobb" gör -- blir de 20 000 orange prickar i en kommun
        # med 2 100 arbetslösa, och loggens u bredvid säger något helt annat.
        self.utanfor = set()
        for iid, st in zip(individer["individual_id"],
                           _kolumn(individer, "status", default="")):
            if str(st) == "not_in_labor_force":
                self.utanfor.add(str(iid))

        for iid, xi, chi, r in zip(individer["individual_id"],
                                   _kolumn(individer, "xi"),
                                   _kolumn(individer, "chi"),
                                   _kolumn(individer, "r_i", "r_o_home")):
            self.ind_geom[str(iid)] = (xi, chi, r)
        for jid in jobb["job_id"]:
            self.jobb_innehavare[str(jid)] = None
            self.jobb_aktivt[str(jid)] = True
            self.jobb_annonserat[str(jid)] = False
        # NÄR JOBBET FÖDDES. Jobb postade under körningen finns i tabellen från
        # början av uppspelningen men ska inte ritas förrän de skapats, annars
        # visar första bildrutan tio års jobbskapande på en gång.
        self.jobb_skapat = {str(j): (0.0 if pd.isna(c) else float(c))
                            for j, c in zip(jobb["job_id"],
                                            _kolumn(jobb, "created_time", default=0.0))}
        for jid, iid in zip(jobb["job_id"], _kolumn(jobb, "individual_id")):
            if not pd.isna(iid):
                self.jobb_innehavare[str(jid)] = str(iid)

    def applicera(self, r):
        h = r.get("event")
        detalj = r.get("event_detail")
        aid = r.get("agent_id")
        jid = r.get("job_id")

        if aid is not None and aid in self.ind_geom:
            xi, chi, r_i = r.get("xi"), r.get("chi"), r.get("r_i")
            if xi not in (None, "None") and chi not in (None, "None"):
                gammal = self.ind_geom[aid]
                try:
                    self.ind_geom[aid] = (
                        float(xi), float(chi),
                        float(r_i) if r_i not in (None, "None") else gammal[2])
                except ValueError:
                    pass

        if h == "start_job" and aid is not None and jid is not None:
            # EN start_job-RAD ÄR INTE ALLTID EN ANSTÄLLNING. handle_start_job
            # kontrollerar att positionen fortfarande är aktiv och ledig när
            # händelsen förfaller -- mellan beslut och tillträde ligger tio
            # till fyrtio dagar -- och returnerar utan att anställa om jobbet
            # hunnit förstöras eller tas. Båda utgångarna loggas som
            # start_job, med detaljen som enda skillnad:
            #
            #   job_gone_before_start                 hon blir arbetslös
            #   job_gone_before_start_kept_previous   hon behåller sitt jobb
            #
            # Uppspelningen läste bara händelsetypen och bokförde en
            # anställning i ett jobb som inte fanns. Felet självläker när hon
            # anställs på riktigt nästa gång, vilket är varför avvikelsen
            # svängde upp och ner kring noll i stället för att växa: den var
            # aldrig ackumulerande, bara ständigt närvarande.
            if str(detalj or "").startswith("job_gone_before_start"):
                return
            # Den som får ett jobb är per definition i arbetskraften.
            self.utanfor.discard(aid)
            tidigare = self.ind_jobb.get(aid)
            if tidigare is not None and tidigare in self.jobb_innehavare:
                self.jobb_innehavare[tidigare] = None
            self.ind_jobb[aid] = jid
            if jid in self.jobb_innehavare:
                self.jobb_innehavare[jid] = aid
                self.jobb_annonserat[jid] = False

        elif h == "destroy_job":
            if detalj == "job_destroyed_holder_displaced" and aid is not None:
                self.ind_jobb[aid] = None
            if jid is not None and jid in self.jobb_aktivt:
                self.jobb_aktivt[jid] = False
                self.jobb_innehavare[jid] = None
                self.jobb_annonserat[jid] = False

        elif detalj in ("career_break", "education_started"):
            # TVÅ SÄTT ATT SLUTA ARBETA UTAN ATT JOBBET FÖRSTÖRS.
            # handle_career_break och handle_start_education nollar båda
            # individens job_id och släpper positionen tillbaka som vakans,
            # men skriver ingen destroy_job-rad. Utan dem räknade
            # uppspelningen personen som fortsatt anställd tills hon anställdes
            # igen -- en långsam överskattning som växte till fem personer över
            # tio år och som aldrig hade synts som ett fel, bara som en
            # marknad som sakta drog ifrån kurvan bredvid.
            # Vilket jobb hon hade vet uppspelningen själv; raden bär inget
            # job_id.
            if aid is not None:
                tidigare = self.ind_jobb.get(aid)
                self.ind_jobb[aid] = None
                if tidigare is not None and tidigare in self.jobb_innehavare:
                    self.jobb_innehavare[tidigare] = None

        elif h == "open_advert" or detalj == "advert_opened":
            if jid is not None and jid in self.jobb_annonserat:
                self.jobb_annonserat[jid] = True

        elif h == "close_vacancy":
            if jid is not None and jid in self.jobb_annonserat:
                self.jobb_annonserat[jid] = False


def _handelsetext(r):
    """En tillsättning i klartext. Det är den form en beslutsfattare läser."""
    hem = r.get("home_municipality")
    jobbkom = r.get("job_municipality")
    try:
        vantan = float(r.get("vacancy_age_days", "nan")) / 30.44
    except (TypeError, ValueError):
        vantan = float("nan")
    delar = []
    if hem and jobbkom and hem != jobbkom:
        delar.append(f"pendlar {hem} \u2192 {jobbkom}")
    elif jobbkom:
        delar.append(f"i {jobbkom}")
    if np.isfinite(vantan):
        delar.append(f"vakansen stod {vantan:.0f} mån")
    return "; ".join(delar)


def _jobbuniversum(run_dir):
    """Alla jobb som funnits under körningen, inte bara de som fanns vid start.

    post_vacancies_batch skapar jobb varje månad mot arbetsgivarnas måltal och
    ger dem id med prefix N. De finns inte i initial_state_jobs.csv. Läses bara
    den saknar exporten varje jobb som fötts under körningen: panelens
    medlemmar syns som anställda utan jobb att peka på i uppgiftsrummet, och
    pendlingsmatrisen tappar deras kommun. I en tioårskörning av Siljan var det
    drygt en tredjedel av de jobb panelen faktiskt tog.

    final_state_jobs.csv bär hela stocken -- förstörda jobb ligger kvar med
    active=False -- så unionen med starttabellen är det fullständiga
    universumet. Starttabellen först, slutet sist: geometrin är densamma, men
    slutraden bär created_time och destroyed_time.
    """
    ini = pd.read_csv(os.path.join(run_dir, "initial_state_jobs.csv"))
    sista = os.path.join(run_dir, "final_state_jobs.csv")
    if os.path.isfile(sista):
        fin = pd.read_csv(sista)
        jobb = pd.concat([ini, fin], ignore_index=True)
        jobb = jobb.drop_duplicates("job_id", keep="last").reset_index(drop=True)
        # INNEHAVAREN TAS UR STARTTABELLEN. Slutradens individual_id är den
        # som håller jobbet vid körningens SLUT. Ärvdes den skulle
        # uppspelningen börja i slutläget och sedan spela upp tio år av
        # händelser ovanpå det.
        start_innehavare = dict(zip(ini["job_id"].astype(str),
                                    ini.get("individual_id", pd.Series(dtype=object))))
        jobb["individual_id"] = [start_innehavare.get(str(j)) for j in jobb["job_id"]]
    else:
        jobb = ini
    jobb["job_id"] = jobb["job_id"].astype(str)
    return jobb


def spela_upp(run_dir, panel_n, panel_jobb_n, seed):
    individer = pd.read_csv(os.path.join(run_dir, "initial_state_individuals.csv"))
    jobb = _jobbuniversum(run_dir)
    individer["individual_id"] = individer["individual_id"].astype(str)

    handelser = read_events(run_dir)
    ts = timeseries_table(handelser)

    tillstand = Tillstand(individer, jobb)

    rng = np.random.default_rng(seed)
    individer["_kommun"] = [_hemkommun(i) for i in individer["individual_id"]]
    if not panel_n or panel_n >= len(individer):
        # HELA POPULATIONEN är förval sedan deltakodningen gjorde den
        # billigare än det gamla urvalet på 2 000. Urvalet var aldrig en
        # modellfråga utan en filstorleksfråga, och det förde med sig en
        # felkälla: punkterna visade ett urval medan talen bredvid gällde
        # alla, och den som räknade prickar fick fel svar.
        panel = individer.reset_index(drop=True)
    else:
        # Urvalet dras STRATIFIERAT PER KOMMUN. Ett obundet urval ur tre
        # kommuner av mycket olika storlek ger nästan inga individer i den
        # minsta, och det är den minsta kommunen tunnheten ska synas i.
        grupper = individer.groupby("_kommun", dropna=False)
        per_grupp = max(1, panel_n // max(len(grupper), 1))
        panel_idx = []
        for _, g in grupper:
            n = min(per_grupp, len(g))
            panel_idx.extend(rng.choice(g.index.to_numpy(), size=n, replace=False))
        # Kommuner mindre än kvoten lämnar ett underskott. Det fylls ur de
        # stora, annars ger --panel 2000 bara 1 700 individer så snart en
        # kommun är liten.
        brist = panel_n - len(panel_idx)
        if brist > 0:
            rest = individer.index.difference(pd.Index(panel_idx))
            if len(rest):
                panel_idx.extend(rng.choice(rest.to_numpy(),
                                            size=min(brist, len(rest)), replace=False))
        panel = individer.loc[sorted(panel_idx)].reset_index(drop=True)
    panel_ids = list(panel["individual_id"])

    # Jobben: alla som någon i panelen håller eller får, plus ett urval av
    # resten, så att uppgiftsrummet inte ser tomt ut runt panelens cirklar.
    panel_set = set(panel_ids)
    rorda_jobb = {str(r["job_id"]) for r in handelser
                  if r.get("event") == "start_job" and r.get("agent_id") in panel_set
                  and r.get("job_id")}
    universum = set(jobb["job_id"])
    # Ett rört jobb som inte finns i universumet är ett tecken på att
    # tabellerna och loggen kommer från olika körningar. Tyst bortfall här var
    # precis det som dolde de nypostade N-jobben.
    saknade = rorda_jobb - universum
    if saknade:
        print(f"[varning] {len(saknade)} jobb-id i loggen saknas i "
              f"tabellerna, t.ex. {sorted(saknade)[:3]}")
    rorda_jobb &= universum
    ovriga = [j for j in jobb["job_id"] if j not in rorda_jobb]
    if not panel_jobb_n:
        valda = set(jobb["job_id"])              # alla jobb, förval
    else:
        n_ovr = min(max(panel_jobb_n - len(rorda_jobb), 0), len(ovriga))
        valda = rorda_jobb | set(rng.choice(ovriga, size=n_ovr, replace=False)) \
            if n_ovr else rorda_jobb
    panel_jobb = jobb[jobb["job_id"].isin(valda)].reset_index(drop=True)
    jobb_ids = list(panel_jobb["job_id"])
    # Position i panelens jobblista. Med list.index() blir varje bildruta
    # panelstorlek gånger jobblistans längd -- 700 miljoner jämförelser över en
    # tioårskörning, och exporten tar längre tid än simuleringen.
    jobb_pos = {j: i for i, j in enumerate(jobb_ids)}

    agg_per_tid = {float(r["time"]): r for _, r in ts.iterrows()} if not ts.empty else {}

    frames = []
    ticker = []
    sedan_forra = []
    ar_nu = None

    # Föregående bildrutas värden, för deltakodningen nedan.
    forra_jobb = [-1] * len(panel_ids)
    forra_geom = [tillstand.ind_geom.get(i, (np.nan, np.nan, np.nan)) for i in panel_ids]

    def bildruta(t, manad, ar):
        nonlocal forra_jobb, forra_geom
        # TILLSTÅNDEN SOM STRÄNGAR, ÖVRIGT SOM DELTAN. Med hela populationen
        # är det här skillnaden mellan 50 och 6 MB. En JSON-array av heltal
        # kostar två tecken per individ och bildruta för kommatecknet allena;
        # en sträng kostar ett tecken totalt. Och xi, chi och r ändras bara
        # när någon utbildar sig -- 10 600 händelser fördelade över 120
        # månader och 20 000 personer -- så att skriva dem varje månad är att
        # lagra samma tal hundratjugo gånger.
        status = []
        jobb_delta = []
        geom_delta = []
        for k, iid in enumerate(panel_ids):
            jid = tillstand.ind_jobb.get(iid)
            status.append("1" if jid else ("2" if iid in tillstand.utanfor else "0"))
            ref = jobb_pos.get(jid, -1) if jid else -1
            if ref != forra_jobb[k]:
                jobb_delta.extend((k, ref))
                forra_jobb[k] = ref
            g = tillstand.ind_geom.get(iid, (np.nan, np.nan, np.nan))
            if g != forra_geom[k]:
                geom_delta.extend((k, _tal(g[0]), _tal(g[1]), _tal(g[2])))
                forra_geom[k] = g

        jstatus = []
        for jid in jobb_ids:
            if tillstand.jobb_skapat.get(jid, 0.0) > t:
                jstatus.append("3")                                 # ej fött än
            elif not tillstand.jobb_aktivt.get(jid, False):
                jstatus.append("2")                                 # inaktivt
            elif tillstand.jobb_innehavare.get(jid):
                jstatus.append("0")                                 # besatt
            else:
                jstatus.append("1")                                 # vakant
        # Pendlingsmatrisen räknas på HELA populationen, inte på panelen.
        # Den ska ställas mot SCB:s tabell `commuting`, och en matris räknad
        # på 2 000 av 30 000 individer är inte jämförbar med den -- en kvot
        # mellan två olika nämnare är ett tal utan tolkning i en dragning.
        pend = {}
        for iid, jid in tillstand.ind_jobb.items():
            if not jid:
                continue
            hem = hemkommun_per_id.get(iid)
            kom = jobbkommun.get(jid)
            if hem and kom:
                pend[f"{hem}>{kom}"] = pend.get(f"{hem}>{kom}", 0) + 1

        a = agg_per_tid.get(float(t), {})
        frames.append({
            "t": round(float(t), 1), "month": manad, "year": ar,
            "workers": {"state": "".join(status),
                        "job_d": jobb_delta, "geom_d": geom_delta},
            "jobs": {"state": "".join(jstatus)},
            "agg": {k: (None if (isinstance(a.get(k), float) and not np.isfinite(a.get(k)))
                        else (round(float(a[k]), 3) if k in a else None))
                    for k in ("employed", "unemployed", "vacancies", "open_vacancies",
                              "active_jobs", "labour_force", "u", "v", "v_open",
                              "tightness")},
            "commuting": pend,
            "events": sedan_forra[-25:],
        })

    jobbkommun = {str(j): str(k) for j, k in
                  zip(jobb["job_id"], _kolumn(jobb, "municipal_code", default=""))}
    # En gång, inte per bildruta: strängdelningen över hela populationen gånger
    # 120 månader är annars miljoner onödiga anrop.
    hemkommun_per_id = {str(i): _hemkommun(i) for i in individer["individual_id"]}

    for r in handelser:
        h = r.get("event")
        if h == "new_month":
            # Bildrutan tas PÅ new_month-raden, inte vid nästa månadsskifte.
            # Aggregaten på raden är stockarna vid månadens ingång; tas
            # tillståndet vid utgången beskriver de två halvorna av samma ruta
            # olika tidpunkter, och panelens sysselsättning stämmer inte med
            # kurvan bredvid.
            bildruta(r["time"],
                     int(float(r.get("month", 0) or 0)), ar_nu)
            sedan_forra = []
        elif h == "new_year":
            # ÅRTALET STÅR BARA PÅ new_year-raden. handle_new_month loggar
            # month men inte year, så varje bildruta fick year: null och
            # tidsaxeln hade behövt räkna månader i stället för att visa
            # årtal. new_year kommer före årets första new_month i kön.
            try:
                ar_nu = int(float(r.get("year")))
            except (TypeError, ValueError):
                pass
        tillstand.applicera(r)
        if (h == "start_job"
                and str(r.get("is_bootstrap", "")).lower() not in ("true", "1")
                and not str(r.get("event_detail") or "").startswith(
                    "job_gone_before_start")):
            txt = _handelsetext(r)
            if txt:
                post = {"t": round(float(r["time"]), 1), "worker": r.get("agent_id"),
                        "occ": r.get("to_onet"), "from_occ": r.get("from_onet"),
                        "text": txt}
                sedan_forra.append(post)
                ticker.append(post)
    return panel, panel_jobb, frames, ticker, individer


# ---------------------------------------------------------------------------
def exportera(run_dir, ut_path, panel_n, panel_jobb_n, seed, db_path):
    panel, panel_jobb, frames, ticker, individer = spela_upp(
        run_dir, panel_n, panel_jobb_n, seed)

    meta = {"schema": SCHEMA_VERSION, "run": os.path.basename(run_dir.rstrip("/")),
            "crs": "EPSG:3006 (SWEREF 99 TM), meter"}
    mp = os.path.join(run_dir, "run_meta.json")
    if os.path.isfile(mp):
        try:
            with open(mp, encoding="utf-8") as f:
                m = json.load(f)
            meta.update({"scenario": m.get("scenario"), "seed": m.get("seed"),
                         "commit": (m.get("git_commit") or "")[:8],
                         "municipalities": [str(k) for k in (m.get("municipalities") or [])]})
        except Exception:
            pass
    koder = set(meta.get("municipalities") or
                {str(k) for k in _kolumn(panel_jobb, "municipal_code", default="")})
    meta["n_months"] = len(frames)
    meta["panel"] = {"workers": len(panel), "jobs": len(panel_jobb),
                     "population": len(individer)}

    data = {
        "meta": meta,
        "municipalities": kommunpolygoner(db_path, koder),
        "deso": desopolygoner(db_path, koder),
        "occupations": yrkesrummet(db_path),
        "municipality_occupations": yrken_per_kommun(panel_jobb),
        "commuting_scb": scb_pendling(db_path, koder),
        "workers": {
            "id": list(panel["individual_id"]),
            "mun": [_hemkommun(i) for i in panel["individual_id"]],
            "x": _rund(_kolumn(panel, "x"), 0),
            "y": _rund(_kolumn(panel, "y"), 0),
            "onet": [str(c) for c in _kolumn(panel, "onet_code", default="")],
        },
        "jobs": {
            "id": list(panel_jobb["job_id"]),
            "mun": [str(k) for k in _kolumn(panel_jobb, "municipal_code", default="")],
            "x": _rund(_kolumn(panel_jobb, "x"), 0),
            "y": _rund(_kolumn(panel_jobb, "y"), 0),
            "xi": _rund(_kolumn(panel_jobb, "xi"), 3),
            "chi": _rund(_kolumn(panel_jobb, "chi"), 3),
            "r_req": _rund(_kolumn(panel_jobb, "r_req"), 3),
            "onet": [str(c) for c in _kolumn(panel_jobb, "onet_code", default="")],
            "wage": _rund(_kolumn(panel_jobb, "wage"), 1),
        },
        "frames": frames,
        "ticker": ticker[:5000],
    }

    os.makedirs(os.path.dirname(os.path.abspath(ut_path)), exist_ok=True)
    with open(ut_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    mb = os.path.getsize(ut_path) / 1e6
    print(f"{ut_path}: {len(frames)} bildrutor, {len(panel)} individer, "
          f"{len(panel_jobb)} jobb, {mb:.1f} MB")
    return ut_path


def main():
    p = argparse.ArgumentParser(description="Exportera en körning för visning.")
    p.add_argument("run_dir", nargs="?", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--panel", type=int, default=0,
                   help="individer att visa; 0 = hela populationen (förval)")
    p.add_argument("--panel-jobs", type=int, default=0,
                   help="jobb att visa; 0 = alla (förval)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--db", default="data/worm.sqlite3", help="för kommunpolygoner")
    a = p.parse_args()

    run_dir = a.run_dir or _senaste_korning()
    ut = a.out or os.path.join("viz", os.path.basename(run_dir.rstrip("/")) + ".json")
    exportera(run_dir, ut, a.panel, a.panel_jobs, a.seed, a.db)


if __name__ == "__main__":
    main()
