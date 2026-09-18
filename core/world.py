# core/world.py

import sys
import os
import numpy as np
import pandas as pd
import traceback
import time

from core.geography.geoworld import GeoWorld
from core.log import log
from core.events import EventQueue
from core.log import EventLogger
from core.occupations.utils import xi_add, chi_add, r_add

DAYS_PER_YEAR = 365.25
MONTH_LENGTHS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def is_leap_year(year):
    return (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))

from core.individual_views import IndividualViews


class World(IndividualViews):
    def __init__(self, db_path, cfg_reader, outdir, geoworld=None, scope=None,
                 individuals=None, jobs=None, employers=None, events=None,
                 participation=None):
        self.db_path = db_path
        self.cfg_reader = cfg_reader
        self.outdir = outdir
        self.scope = scope
        self.geoworld = geoworld if geoworld is not None else GeoWorld(db_path)
        # Deltagandeprofilen per kommun, byggd av ScenarioBuilder vid
        # uppstart. Utträdet vid årsskiftet räknas ur SAMMA kurva som
        # fördelningen drogs ur -- två kurvor för samma sak hade kunnat glida
        # isär, och de skulle göra det tyst.
        self.participation = participation or {}
        self.individuals = individuals if individuals is not None else pd.DataFrame()
        self.jobs = jobs if jobs is not None else pd.DataFrame()
        self.employers = employers if employers is not None else pd.DataFrame()
        self.events = events if events is not None else pd.DataFrame(columns=["time", "agent_id", "event_type", "params"])
        self.current_time = 0

        self.event_queue = EventQueue()
        self.event_logger = EventLogger(filepath=os.path.join(outdir, "eventlog.csv"))
        self._matchings = pd.DataFrame()
        self.n_matched_in_month = 0
        self.simulation_end_time = self._get_simulation_end_time()

    @property
    def conn(self):
        """Lat sqlite-anslutning. Saknades helt sedan jobbflödena infördes:
        _geom_lookup och _draw_occupation_for_employer föll tyst i try/except
        och u_R_occ kunde aldrig beräknas."""
        if getattr(self, "_conn", None) is None and getattr(self, "db_path", None):
            import sqlite3
            self._conn = sqlite3.connect(self.db_path)
        return getattr(self, "_conn", None)

    @conn.setter
    def conn(self, value):
        self._conn = value

    def n_years(self):
        """Körningens längd, läst på ETT ställe.

        Slutdatumet läste toppnivån först medan kalendern bara läste
        simulation-blocket och föll tillbaka på sin egen default fem. Med
        n_years: 10 på toppnivån -- där det står i scenariofilerna -- körde
        simuleringen tio år med fem års kalender: sista new_month låg på dag
        1796 och sedan hoppade loggen till simulation_completed vid 3652.50.
        Under år sex till tio fanns inga månadsskiften, inga årsskiften, inga
        tvärsnitt och INGEN LÖNEREVISION. Halva körningen gick utan sin
        bokföring, och konvergenskontrollen mätte ingenting.

        Defaulten fem var det som gjorde felet tyst. Saknas parametern helt är
        det ett fel, inte ett värde att gissa.
        """
        cfg = self.cfg_reader.config
        n = cfg.get('n_years')
        if n is None:
            n = cfg.get('simulation', {}).get('n_years')
        if n is None:
            raise KeyError("n_years saknas i scenariot: körningens längd kan "
                           "inte gissas.")
        return int(n)

    def _get_simulation_end_time(self):
        return DAYS_PER_YEAR * self.n_years()

    def _check_calendar_covers_run(self):
        """Kalendern ska räcka hela vägen. Går den ut i förtid tystnar
        månadsskiften, årliga tvärsnitt och lönerevisionen medan
        individhändelserna fortsätter -- och utfallet ser normalt ut."""
        senaste = max((post[0] for post in getattr(self.event_queue, 'queue', [])
                       if (post[2] if isinstance(post, tuple) else post)
                       .get('event_type') in ('new_month', 'new_year')),
                      default=None)
        if senaste is None:
            return
        if senaste < self.simulation_end_time - 40.0:
            raise RuntimeError(
                f"kalendern slutar dag {senaste:.0f} men körningen dag "
                f"{self.simulation_end_time:.0f}: månadsskiften, tvärsnitt och "
                "lönerevision skulle saknas i resten av körningen.")

    def _skatta_relevansfordelningar(self):
        """Fördelningen över relevansmängden för uppstartens arbetslösa.

        bli_arbetslos skattar den för var och en som blir arbetslös under
        körningen, men uppstartens kohort blir aldrig arbetslös -- de ÄR det
        från början. Utan skattningen faller de tillbaka på den
        personrelativa sigmoiden, och i en körning var de fyra femtedelar av
        stocken.

        En gång, före första händelsen. Kostnaden är ett svep över
        vakansstocken per individ, alltså samma arbete som en sökning, och
        körningen gör 700 000 sökningar.
        """
        ind = self.individuals
        if 'w_rel_med' not in ind.columns or 'status' not in ind.columns:
            return
        from core.matching_core import relevansfordelning
        mask = ((ind['status'] == 'unemployed')
                & ind['w_rel_med'].isna()).to_numpy()
        if not mask.any():
            return
        from math import erf, sqrt
        n_ok = 0
        for idx in ind.index[mask]:
            try:
                f = relevansfordelning(self, idx)
            except Exception:
                f = None
            if not f:
                continue
            med, sd, _n = f
            ind.at[idx, 'w_rel_med'] = med
            ind.at[idx, 'w_rel_sd'] = sd
            w_last = float(ind.at[idx, 'w_last']) if 'w_last' in ind.columns else float('nan')
            if np.isfinite(w_last) and w_last > 0 and sd > 0:
                z = (np.log(w_last) - np.log(med)) / sd
                p0 = 0.5 * (1.0 + erf(z / sqrt(2.0)))
                ind.at[idx, 'p_claim0'] = float(min(max(p0, 0.01), 0.995))
            n_ok += 1
        print(f"[reservation] relevansfördelning skattad för {n_ok} av "
              f"{int(mask.sum())} arbetslösa vid uppstart")

    def simulate(self):
        from core.event_handlers import RULE_SWITCH
        self.wallclock_start = time.time()
        self._skatta_relevansfordelningar()
        self._init_events()
        self._check_calendar_covers_run()
        n_handelser = 0
        while not self.event_queue.is_empty():
            event = self.event_queue.pop()
            if event["time"] > self.simulation_end_time:
                break
            handler = RULE_SWITCH[event["event_type"]]
            handler(event, self)
            n_handelser += 1

        # MÄTNINGEN AVSLUTAS. wallclock_start sattes här sedan länge men lästes
        # aldrig någonstans: klockan startades och stannades aldrig, och
        # körtiden fick uppskattas ur skillnaden mellan run_meta.json:s
        # "started" och registryraden -- sekundupplösning, och hela
        # scenariobygget inräknat. Talet hör hemma på raden, så att en
        # prestandaregression syns i samma tabell som allt annat i stället
        # för i minnet av hur lång tid förra körningen kändes.
        sekunder = time.time() - self.wallclock_start
        self.sim_seconds = round(sekunder, 1)
        event = {
            "time": self.simulation_end_time,
            "agent_id": None,
            "event_type": "simulation_completed",
            "params": {}
        }
        self.event_logger.log_event(
            self, event, print_line=True,
            extra={"wallclock_seconds": round(sekunder, 1),
                   "n_events_handled": n_handelser,
                   "events_per_second": round(n_handelser / sekunder, 1)
                   if sekunder > 0 else None})

        self.close()

    def tick(self):
        self._apply_decision_rules()
        self._process_due_events()

    def _apply_decision_rules(self):
        unemployed = self.individuals[self.individuals['status'] == 'unemployed']
        # Kolumner som reservationslönen behöver. Garanteras här så att en
        # körning mot ett äldre starttillstånd inte faller på en saknad
        # kolumn: w_last är NaN för den som aldrig varit anställd, och
        # unemployed_since NaN för den som inte är arbetslös.
        for kol in ('w_last', 'unemployed_since', 'pi_o',
                    'w_rel_med', 'w_rel_sd', 'p_claim0', 'w_res_time',
                    'last_education_draw'):
            if kol not in self.individuals.columns:
                self.individuals[kol] = np.nan

        if 'next_job_search_time' in self.individuals.columns:
            ready = unemployed[unemployed['next_job_search_time'] <= self.current_time]
        else:
            ready = unemployed

        for idx in ready.index:
            event = {
                "time": self.current_time,
                "agent_id": idx,
                "event_type": "start_job_search",
                "params": {}
            }
            self._push_event(event)

    def _process_due_events(self):
        from core.event_handlers import RULE_SWITCH
        while not self.event_queue.is_empty() and self.event_queue.peek()["time"] <= self.current_time:
            event = self.event_queue.pop()
            handler = RULE_SWITCH.get(event["event_type"])
            if handler is None:
                print(f"Unknown event: {event['event_type']}")
                continue
            try:
                handler(event, self)
            except Exception as e:
                print(f"[FATAL] Exception in handler for event {event['event_type']} (agent {event['agent_id']}): {e}")
                traceback.print_exc()
                raise

    def _push_event(self, event):
        if event["time"] is None:
            print(f"VARNING: Försöker pusha event utan tidsstämpel: {event['event_type']}")
            return
        if event["time"] < self.simulation_end_time:
            self.event_queue.push(event)

    def close(self):
        self.event_logger.close()

    # ------------------------------------------------------------------
    # Jobbflöden: jobb föds och dör. Utan detta är antalet jobb konstant och
    # Beveridgekurvan en bokföringsidentitet (v linjär i u).
    # ------------------------------------------------------------------
    def _job_flow_cfg(self):
        sim = self.cfg_reader.config.get('simulation', {})
        return {
            'enabled': bool(sim.get('job_flows', False)),
            'delta': float(sim.get('job_destruction_rate', 0.10)),   # per år
            'fill_rate': float(sim.get('vacancy_fill_rate', 0.25)),  # andel av underskott per månad
            'growth': float(sim.get('employer_growth_rate', 0.0)),   # per år, mål-tillväxt
        }

    def _init_job_flows(self):
        """Ger jobben active/created_time och arbetsgivarna ett måltal."""
        # individual_id måste vara object: är kolumnen float64 (enbart NaN)
        # höjer pandas 2.x TypeError när ett sträng-id skrivs in. I praktiken
        # räddas det av batch-matchningen vid t=0, men en händelsedriven
        # anställning i en värld utan föregående batch skulle falla.
        if 'individual_id' in self.jobs.columns and self.jobs['individual_id'].dtype != object:
            self.jobs['individual_id'] = self.jobs['individual_id'].astype(object)
        if 'vacant_since' not in self.jobs.columns:
            # När positionen senast blev ledig. created_time säger när jobbet
            # skapades, vilket är något annat: en position som fyllts och
            # tömts flera gånger är inte gammal som vakans. Utan detta går
            # vakansernas ÅLDERSFÖRDELNING inte att mäta, och det är den som
            # skiljer en växande stock av samma positioner från ett växande
            # flöde.
            self.jobs['vacant_since'] = 0.0
        if 'pending' not in self.jobs.columns:
            # Tillsatt men ännu inte tillträtt. Positionen är en öppen vakans i
            # statistiken men får inte sökas av någon annan.
            self.jobs['pending'] = False
        if 'active' not in self.jobs.columns:
            self.jobs['active'] = True
            self.jobs['created_time'] = float(self.current_time)
            self.jobs['destroyed_time'] = np.nan
        if 'target_size' not in self.employers.columns:
            counts = self.jobs[self.jobs['active']].groupby('employer_id').size()
            self.employers['target_size'] = (
                self.employers['employer_id'].map(counts).fillna(0).astype(float))
        self._next_job_seq = len(self.jobs)

    def _schedule_destruction(self, job_ids, t_now):
        """Exponentiell livslängd med hasard delta (per år)."""
        cfg = self._job_flow_cfg()
        if not cfg['enabled'] or cfg['delta'] <= 0 or len(job_ids) == 0:
            return
        scale = 365.25 / cfg['delta']
        lifetimes = np.random.exponential(scale, size=len(job_ids))
        for job_id, life in zip(job_ids, lifetimes):
            self._push_event({
                "time": float(t_now + life),
                "agent_id": None,
                "event_type": "destroy_job",
                "params": {"job_id": job_id},
            })

    def post_vacancies_batch(self, t_now):
        """Skapar nya jobb mot arbetsgivarnas måltal. Körs en gång per månad.

        Underskott = mål - aktiva jobb. En andel fill_rate av underskottet
        postas varje månad, vilket ger en stock av vakanser i omlopp i stället
        för omedelbar återfyllnad. Måltalet växer med growth (0 = stationärt);
        en teknologichock sänker måltalet, vilket är hur chocken förstör jobb.
        """
        cfg = self._job_flow_cfg()
        if not cfg['enabled']:
            return 0
        jobs = self.jobs
        active = jobs[jobs['active']]
        n_active = active.groupby('employer_id').size()
        emp = self.employers
        if cfg['growth']:
            emp['target_size'] = emp['target_size'] * (1.0 + cfg['growth'] / 12.0)
        target = emp.set_index('employer_id')['target_size']
        deficit = (target - n_active.reindex(target.index).fillna(0)).clip(lower=0)
        # Stokastisk avrundning: floor() skulle nolla alla underskott under
        # 1/fill_rate, vilket systematiskt kväver jobbskapandet hos små
        # arbetsgivare (i Mora är 681 av 792 mikroföretag).
        expected = deficit * cfg['fill_rate']
        base = np.floor(expected)
        n_new = (base + (np.random.random(len(expected)) < (expected - base))).astype(int)
        n_new = n_new[n_new > 0]
        if n_new.empty:
            return 0

        # Mall per arbetsgivare ur ALLA jobb, inte bara aktiva: en arbetsgivare
        # som tillfälligt förlorat alla sina positioner måste kunna posta igen
        # (annars dör mikroföretag permanent vid första förstörelsen).
        proto = jobs.drop_duplicates('employer_id', keep='last').set_index('employer_id')
        # Arbetsställets svenska yrken och deras O*NET-realisering, ur ALLA
        # dess jobb. Ett nytt jobb i ett yrke som redan finns där får samma
        # kod (core/bransch.py, Kommunprofil.onet).
        realiserat = {}
        if 'ssyk_code' in jobs.columns:
            har = jobs[jobs['employer_id'].isin(n_new.index) & jobs['ssyk_code'].notna()]
            for (e, s_), kod in har.groupby(['employer_id', 'ssyk_code'])['onet_code'].first().items():
                realiserat.setdefault(e, {})[str(s_)] = kod
        rows, new_ids = [], []
        for employer_id, k in n_new.items():
            if employer_id not in proto.index:
                continue
            base = proto.loc[employer_id]
            egna = realiserat.setdefault(employer_id, {})
            for _ in range(int(k)):
                ssyk_code, onet_code = self._draw_occupation_for_employer(base, egna)
                geom = self._geom_lookup(onet_code)
                jid = f"N{self._next_job_seq:07d}"      # N = nypostad, undviker krock
                self._next_job_seq += 1
                row = base.to_dict()
                row.update({
                    "job_id": jid, "employer_id": employer_id, "individual_id": None,
                    "onet_code": onet_code, "ssyk_code": ssyk_code, "active": True,
                    # Mallen kopierar ALLA kolumner. Utan denna rad ärver ett
                    # nyskapat jobb mallens pending-flagga och föds osökbart:
                    # det räknas som vakans men kan aldrig tillsättas. Över fem
                    # år lade det 3 688 döda vakanser i Mora medan
                    # sysselsättningen föll från 9 900 till 6 505.
                    "pending": False,
                    # Samma sak för vacant_since: ur mallen ärvde det nya
                    # jobbet den GAMLA positionens tidsstämpel, oftast 0.0
                    # från starten. Vakansernas medianålder vid tillsättning
                    # blev 1 956 dagar -- inte för att samma positioner stod
                    # öppna, utan för att nypostade jobb föddes fem år gamla.
                    "vacant_since": float(t_now),
                    "created_time": float(t_now), "destroyed_time": np.nan,
                })
                if geom is not None:
                    row.update(geom)
                # geom ger yrkets fältlön; arbetsgivareffekten är en egenskap
                # hos arbetsgivaren och följer med mallen, som är samma
                # arbetsgivare. Utan detta tappar nypostade jobb eta och
                # betalar yrkets normallön oavsett var de sitter.
                if "wage_eta" in row and pd.notna(row.get("wage_eta")):
                    row["wage"] = float(row["wage"]) * float(np.exp(row["wage_eta"]))
                rows.append(row); new_ids.append(jid)
        if not rows:
            return 0
        self.jobs = pd.concat([jobs, pd.DataFrame(rows)], ignore_index=True)
        self._schedule_destruction(new_ids, t_now)
        return len(rows)

    def jobb_kommun(self):
        """Jobbens kommunkod som nollutfylld sträng, cachad per tabellängd."""
        n = len(self.jobs)
        if getattr(self, "_jk_n", None) != n:
            self._jk = self.jobs["municipal_code"].astype(str).str.zfill(4).to_numpy()
            self._jk_n = n
        return self._jk

    def omgivning(self):
        """Omgivningen för scenariots kommuner (core/omgivning.py), en gång."""
        if not hasattr(self, "_omgivning"):
            from core.omgivning import Omgivning
            self._omgivning = Omgivning(self.conn, self.cfg_reader.config.get("municipalities", []))
        return self._omgivning

    def kommunprofil(self):
        if not hasattr(self, "_profil"):
            from core.bransch import Kommunprofil
            self._profil = Kommunprofil(self.conn)
        return self._profil

    def skapa_externt_jobb(self, t_now, kommun, bransch, ssyk, onet_code, x, y):
        """Ett jobb utanför regionen, för en utpendlare (docs/omgivning.md, O4).

        Ingen arbetsgivare och ingen vakans: raden är utlovad (pending) från
        start och upphör när den lämnas (set_job_filled). Den förstörs i samma
        takt som regionens jobb. Lönen är yrkets pris i fältet, utan
        arbetsgivareffekt."""
        geom = self._geom_lookup(onet_code) or {}
        if not hasattr(self, "_next_ext_seq"):
            self._next_ext_seq = 0
        jid = f"X{self._next_ext_seq:07d}"
        self._next_ext_seq += 1
        rad = {c: None for c in self.jobs.columns}
        rad.update(geom)
        rad.update({"job_id": jid, "employer_id": None, "individual_id": None,
                    "municipal_code": str(kommun).zfill(4), "sni_code": bransch,
                    "ssyk_code": ssyk, "onet_code": onet_code, "core_ssyk": None,
                    "x": float(x), "y": float(y), "active": True, "pending": True,
                    "extern": True, "vacant_since": float(t_now),
                    "employer_size": np.nan, "wage_eta": 0.0})
        self.jobs = pd.concat([self.jobs, pd.DataFrame([rad])], ignore_index=True)
        self._schedule_destruction([jid], t_now)
        return jid

    def _draw_occupation_for_employer(self, base_row, realiserade=None):
        """(ssyk, O*NET) för ett nytt jobb: kommunens profil i arbetsställets
        bransch, viktad mot arbetsställets kärnyrke (core/bransch.py,
        Kommunprofil.dra_nytt). Vid start fördelades en pool; under körning
        dras yrket, så kommunens profil bevaras i väntevärde.

        Tidigare drogs nya jobb ur KOMMUNENS yrkesfördelning oavsett
        arbetsställe, så en läkare kunde postas på en bilverkstad, och före
        det ärvde de mallens yrke, så arbetsgivaren drev mot monokultur. Mallen
        bär nu bara kommun, bransch och kärna; yrket dras på nytt.

        realiserade är arbetsställets svenska yrken och deras O*NET-kod; ett
        yrke som redan finns där behåller sin kod."""
        if self.conn is None:                   # syntetisk värld utan databas
            return base_row.get("ssyk_code"), base_row.get("onet_code")
        karna = base_row.get("core_ssyk")
        karna = None if karna is None or (isinstance(karna, float) and np.isnan(karna)) else str(karna)
        profil = self.kommunprofil()
        ssyk = profil.dra_nytt(base_row["municipal_code"], base_row["sni_code"],
                               karna, np.random)
        return ssyk, profil.onet(ssyk, np.random, realiserade)

    def _geom_lookup(self, onet_code):
        """Yrkets geometri, pris OCH kravintensitet.

        r_req måste vara med. Ett nytt jobb får ett nytt yrke ur
        _draw_occupation_for_employer men byggs ur en mall med
        row = base.to_dict(); saknas r_req här behåller jobbet MALLENS krav
        medan position, radie och lön kommer från det nya yrket. Position och
        pris ur ett yrke, krav ur ett annat, utan NaN och utan varning. Felet
        ärvs dessutom vidare, eftersom mallen är den sist tillagda raden per
        arbetsgivare, och växer därför under körningen.

        Det tidigare 'except Exception: _geom_df = None' dolde samma sak en
        gång till: en trasig eller gammal tabell gav tyst noll geometri åt
        alla nya jobb. En värld utan databas (syntetiska tester) är ett
        legitimt fall och behandlas för sig; ett SQL-fel är det inte.
        """
        if not hasattr(self, "_geom_df"):
            if self.conn is None:
                self._geom_df = None
            else:
                self._geom_df = pd.read_sql(
                    "SELECT onet_code, chi, xi, x_occ, y_occ, r_o, w_rel, r_req, "
                    "geom_source FROM onet_occupation_space",
                    self.conn).set_index("onet_code")
        if self._geom_df is None or onet_code not in self._geom_df.index:
            return None
        r = self._geom_df.loc[onet_code]
        return {"chi": float(r["chi"]), "xi": float(r["xi"]),
                "x_occ": float(r["x_occ"]), "y_occ": float(r["y_occ"]),
                "r_o": float(r["r_o"]), "geom_source": str(r["geom_source"]),
                "wage": float(r["w_rel"]) if pd.notna(r["w_rel"]) else 1.0,
                "r_req": float(r["r_req"]) if pd.notna(r["r_req"]) else np.nan}

    def prepare(self):
        """Jobbkolumner och kompetenscirklar. Idempotent.

        Låg tidigare bara i _init_events, som körs FÖRST I simulate() -- alltså
        efter uppstarten. Den gamla batch-matchningen behövde varken active,
        pending eller cirklar, så ordningen fungerade av en slump. Uppstarten i
        0069 är samma kod som körningen och behöver allt tre: utan active föll
        handle_start_job på KeyError vid första tillträdet.

        Vakterna 'if ... not in columns' fanns redan, så den går att anropa två
        gånger. bootstrap_matching anropar den, och simulate() gör det igen.
        """
        self._init_job_flows()
        if 'next_search_time' not in self.individuals.columns:
            # EN söktidpunkt per individ. Fram till 0087 var sökningen kedjor av
            # händelser som startades på fyra ställen och dog på ett: den
            # anställdes kedja slutade vid första torra sökning, och varje
            # separation lade en ny kedja utan att fråga om en levde.
            # Sökintensiteten var en följd av personens historia, inte av
            # parametern. Nu äger individen sin nästa sökning; en händelse vars
            # 'due' inte längre är hennes next_search_time är ersatt och kastas.
            self.individuals['next_search_time'] = np.nan
        if 'accepted_job_id' not in self.individuals.columns:
            # ETT LÖFTE I TAGEN (0098): den accepterade men ännu ej tillträdda
            # positionen. Skapas här och inte vid första acceptansen, så att
            # _behörig kan lita på att kolumnen finns.
            self.individuals['accepted_job_id'] = pd.Series(
                [None] * len(self.individuals), index=self.individuals.index,
                dtype="object")
        # Lönen och revisionens utgångspunkt hör till individens SCHEMA, inte
        # till någon enskild funktion. De skapades tidigare i
        # _seed_wages_for_matched, som utgick med 0069, och då fanns ingen
        # producent kvar: vakten "if 'w_neg' in ind.columns" i apply_once blev
        # falsk vid varje anställning, precis som i 0068. Samma tysta vakt,
        # samma fel, andra gången. Kolumnerna skapas här, tillsammans med
        # jobbens active och pending, och skrivningen sker utan vakt.
        for kol in ("w_neg", "q_last"):
            if kol not in self.individuals.columns:
                self.individuals[kol] = np.nan
        # Objekt, inte float: notice_job_id bär ett job_id under uppsägningen
        if "notice_job_id" not in self.individuals.columns:
            self.individuals["notice_job_id"] = pd.Series(
                [None] * len(self.individuals), index=self.individuals.index,
                dtype="object")
        # OMGIVNINGEN (docs/omgivning.md). En extern individ är en inpendlare,
        # ett externt jobb ett jobb utanför regionen som en utpendlare har.
        # Kolumnerna hör till schemat, så att bokföringen alltid kan skilja
        # regionens egna från randens; ingen skapas förrän flödena finns (O3, O4).
        # Alltid boolesk: när regionens invånare slås ihop med reservoaren får
        # invånarna NaN, och bool(NaN) är sant -- utpendlingen behandlade då
        # varje invånare som extern och gav ingen utpendlare alls.
        for tabell in (self.individuals, self.jobs):
            if "extern" not in tabell.columns:
                tabell["extern"] = False
            else:
                tabell["extern"] = tabell["extern"].fillna(False).astype(bool)
        if "onet_code" in self.individuals.columns and not hasattr(self, "circles"):
            self.init_competence()
        self.refresh_ind()

    def census_open_vacancies(self, t_now):
        """Folkräkning av de LEDIGA positionerna, per åldersintervall.

        Väntetiden i advert_opened är CENSURERAD: den loggas när den första
        ansökan kommer, och en vakans som aldrig får någon loggar ingenting.
        Svansen består av just dem, så medelvärdet 33-37 dagar är räknat på de
        överlevande och underskattar. Folkräkningen har inte det problemet --
        den ser stocken som den är, varje månad -- och bär de egenskaper som
        skiljer en position som väntar ett år från en som fylls på fyrtio
        dagar: kravnivå, arbetsgivarstorlek, kommun, antal ansökningar hittills.

        Fyra rader per månad, 480 på en tioårskörning.
        """
        jobs = self.jobs
        if 'active' not in jobs.columns or 'vacant_since' not in jobs.columns:
            return
        ledig = (jobs['individual_id'].isna() & jobs['active'].fillna(False).astype(bool)
                 & ~jobs.get('pending', False).fillna(False).astype(bool))
        if not ledig.any():
            return
        d = jobs.loc[ledig]
        alder = float(t_now) - pd.to_numeric(d['vacant_since'], errors='coerce')
        kanter = [(0.0, 40.0), (40.0, 90.0), (90.0, 180.0), (180.0, np.inf)]
        for lo, hi in kanter:
            m = (alder >= lo) & (alder < hi)
            if not m.any():
                continue
            grupp = d.loc[m.values]
            extra = {"event_detail": "vacancy_census",
                     "age_bucket": f"{int(lo)}-{'inf' if hi == np.inf else int(hi)}",
                     "n": int(len(grupp)),
                     "age_mean": round(float(alder[m].mean()), 1)}
            if 'r_req' in grupp.columns:
                extra["r_req_mean"] = round(float(pd.to_numeric(
                    grupp['r_req'], errors='coerce').mean()), 4)
            if 'employer_size' in grupp.columns:
                extra["employer_size_median"] = round(float(pd.to_numeric(
                    grupp['employer_size'], errors='coerce').median()), 1)
            if 'municipal_code' in grupp.columns:
                topp = grupp['municipal_code'].astype(str).value_counts()
                extra["municipality_top"] = str(topp.index[0])
                extra["municipality_top_share"] = round(float(topp.iloc[0] / len(grupp)), 3)
            # applications skapas lat vid första ansökan; inga ansökningar alls
            # är ett giltigt tillstånd och inte ett fel.
            ans = getattr(self, 'applications', {})
            extra["n_applications"] = int(sum(len(ans.get(j, [])) for j in grupp['job_id']))
            self.event_logger.log_event(
                self, {"time": float(t_now), "agent_id": None,
                       "event_type": "vacancy_census"}, extra=extra)

    def search_interval(self, idx, t_now, first=False):
        """Nästa söktidpunkt för individen, ur status.

        Arbetslös: exponentiellt intervall med medel search_interval (28 d).
        Anställd: samma gånger on_the_job_search_factor; vid tillträde
        (first=True) läggs rampen on_the_job_search_ramp_days framför -- den
        gällde tidigare bara uppstartens bestånd. Utanför arbetskraften eller i
        utbildning: None, ingen sökning schemaläggs."""
        status = self.individuals.at[idx, 'status']
        sim = self.cfg_reader.config.get('simulation', {})
        timing = self.cfg_reader.get_event_timing('start_job_search')
        if status == 'unemployed':
            factor, lead = 1.0, 0.0
        elif status == 'employed':
            factor = float(sim.get('on_the_job_search_factor', 5.0))
            # DEN UNDERBETALDA SÖKER OFTARE. Att hon byter oftare följde förut
            # bara av att fler positioner gav positivt överskott -- men
            # sökintensiteten var konstant oavsett om hon låg under yrkets
            # pris. Verklighetens undersköterska med lön under Pi för vård
            # söker mer, inte lika mycket. Intervallet kortas med
            # 1 + gamma * (Pi - w) / Pi, avkortat nedåt vid noll: den som
            # ligger över Pi söker inte mindre än normalt.
            gamma = float(sim.get('underpay_search_gamma', 0.0))
            if gamma > 0:
                try:
                    pi_o = float(self.individuals.at[idx, 'pi_o'])
                    w = float(self.individuals.at[idx, 'w_res'])
                except (KeyError, TypeError, ValueError):
                    pi_o, w = float('nan'), float('nan')
                if np.isfinite(pi_o) and pi_o > 0 and np.isfinite(w):
                    factor = factor / (1.0 + gamma * max(0.0, (pi_o - w) / pi_o))
            lead = float(sim.get('on_the_job_search_ramp_days', 180.0)) if first else 0.0
        elif status == 'extern':
            # Inpendlingsreservoaren (docs/omgivning.md): arbetar i
            # omgivningen och söker regionens vakanser med en egen takt, som
            # kalibreras mot matrisens inpendlingsstock (O5).
            factor = float(sim.get('inpendling_sokfaktor',
                                   sim.get('on_the_job_search_factor', 5.0)))
            lead = 0.0
        else:
            return None
        if timing['dist'] == 'exponential':
            interval = np.random.exponential(timing['mean'] * factor)
        elif timing['dist'] == 'uniform':
            interval = np.random.uniform(timing['min'], timing['max']) * factor
        else:
            raise ValueError(f"okänd fördelning för start_job_search: {timing['dist']}")
        return float(t_now + lead + interval)

    def schedule_search(self, idx, t_next):
        """Sätter individens nästa sökning och lägger händelsen. Ett anrop
        ersätter alltid det föregående: händelsen bär 'due', och
        handle_start_job_search kastar den om due != next_search_time."""
        if t_next is None:
            return
        self.individuals.at[idx, 'next_search_time'] = float(t_next)
        self._push_event({"time": float(t_next), "agent_id": idx,
                          "event_type": "start_job_search",
                          "params": {"due": float(t_next)}})

    def _init_events(self):
        self.prepare()
        if self._job_flow_cfg()['enabled']:
            self._schedule_destruction(self.jobs.loc[self.jobs['active'], 'job_id'].tolist(),
                                       self.current_time)
        # quit_job schemaläggs INTE längre. Den var en exogen avgång,
        # normalfördelad kring sju år, som gjorde omkring 1 250 personer
        # arbetslösa per år utan orsak -- och som drev vakansstocken från 625
        # till 1 460 över tio år. Få slutar utan att ha något nytt att gå
        # till. quit_job är nu en KONSEKVENS av ett erbjudande
        # (handle_close_vacancy), och den sällsynta avgången utan något att gå
        # till bärs av career_break.

        # Sökimpulsen gäller HELA arbetskraften. Anställda söker också, med
        # egen takt: on_the_job_search_factor gånger den arbetslösas intervall.
        # Sökningen från anställning är det som gör att en position kan bli
        # ledig utan att någon blir arbetslös.
        # Samma funktion som körningen: uppstartens bestånd får rampen som
        # ett tillträde vid t = 0 (first=True).
        mask = self.individuals['status'].isin(('unemployed', 'employed', 'extern'))
        for idx in self.individuals.index[mask]:
            self.schedule_search(idx, self.search_interval(idx, 0.0, first=True))

        # Schemalägg kalenderhändelser (new_month, new_year)
        self.schedule_calendar_events()

    def schedule_calendar_events(self):
        n_years = self.n_years()
        start_year = self.cfg_reader.config.get('simulation', {}).get('start_year', 2024)
        start_month = self.cfg_reader.config.get('simulation', {}).get('start_month', 1)

        day = 0
        # Lägg till new_year för startåret
        event = {
            "time": day,
            "agent_id": None,
            "event_type": "new_year",
            "params": {"year": start_year}
        }
        self._push_event(event)

        for y in range(n_years):
            current_year = start_year + y
            months_in_year = list(range(1, 13))
            if y == 0 and start_month > 1:
                months_in_year = list(range(start_month, 13))
            for current_month in months_in_year:
                event = {
                    "time": day,
                    "agent_id": None,
                    "event_type": "new_month",
                    "params": {"year": current_year, "month": current_month}
                }
                self._push_event(event)
                # Räkna ut dagar i månaden
                if current_month == 2 and is_leap_year(current_year):
                    days_in_month = 29
                else:
                    days_in_month = MONTH_LENGTHS[current_month - 1]
                day += days_in_month
            # Lägg till new_year för nästa år (utom sista året)
            if y < n_years - 1:
                event = {
                    "time": day,
                    "agent_id": None,
                    "event_type": "new_year",
                    "params": {"year": current_year + 1}
                }
                self._push_event(event)

    # ------------------------------------------------------------------
    # Kompetenscirklar (docs/individmodell.md, avsnitt 2)
    # ------------------------------------------------------------------
    def competence_params(self):
        from core.occupations.competence import CompetenceParams
        if not hasattr(self, "_cp"):
            self._cp = CompetenceParams.from_config(
                self.cfg_reader.config.get("simulation", {}))
        return self._cp

    def init_competence(self):
        """Bygger startpopulationens cirklar ur onet_code, education_level och
        tenure_years, och skriver de härledda måtten till individtabellen."""
        from core.occupations.competence import Circles, seed_circles
        ind = self.individuals
        p = self.competence_params()
        self.circles = Circles(len(ind), p.K)
        codes = ind["onet_code"].to_numpy() if "onet_code" in ind.columns else [None] * len(ind)
        xs = ind["x_occ"].to_numpy(float); ys = ind["y_occ"].to_numpy(float)
        ro = (ind["r_o_home"].to_numpy(float) if "r_o_home" in ind.columns
              else np.full(len(ind), 0.27))
        ten = (ind["tenure_years"].to_numpy(float) if "tenure_years" in ind.columns
               else np.full(len(ind), 5.0))
        edu = (ind["education_level"].to_numpy() if "education_level" in ind.columns
               else np.full(len(ind), 0))
        for i in range(len(ind)):
            e = edu[i]
            try:
                e = int(float(e))
            except (TypeError, ValueError):
                e = 0
            seed_circles(self.circles, i, codes[i], xs[i], ys[i], ro[i], ten[i], e, p)
        self._active_slot = np.full(len(ind), -1, dtype=np.int64)
        st = ind["status"].to_numpy() if "status" in ind.columns else None
        if st is not None:
            # extern: reservoaren arbetar i omgivningen, i sitt eget yrke
            for i in np.flatnonzero((st == "employed") | (st == "extern")):
                if codes[i] is not None and not (isinstance(codes[i], float) and np.isnan(codes[i])):
                    self._active_slot[i] = self.circles.latest(i, str(codes[i]))
        self._write_competence_summary()

    def _write_competence_summary(self):
        """Skriver om HELA kolumnerna x_occ, y_occ, chi, xi, r_i, R.

        Anropas varje månad ur evolve_competence, vid uppstart och vid
        omskolning. En hel kolumn tilldelad byter block i pandas, så
        kolumnvyerna (0110) tappar kontakten -- verifieringen vid
        månadsskiftet fångade det på första månaden. Vyerna byggs därför om
        här, direkt efter skrivningen, i stället för att upptäckas senare."""
        summ = self.circles.summarize()
        ind = self.individuals
        for col in ("x_occ", "y_occ", "chi", "xi", "r_i"):
            ind[col] = summ[col]
        ind["R"] = summ["R"]
        # Till individtabellen så att slutläget bär dem; årsraden bär
        # fördelningen (_circle_stats).
        ind["n_circles"] = self.circles.counts()
        self.refresh_ind()

    def set_active_occupation(self, idx, onet_code, x, y, r_o):
        """Anropas vid tillträde. Varje anställning är en händelse och får en
        egen cirkel utan massa; den får exponering i kommande månadssteg, och
        alla cirklar i yrket skärps.

        Uppstartens anställning i det egna startyrket fortsatte tidigare
        startcirkeln (steg 3). Primingen (core/priming.py, 6a-i) flyttar nu
        tjänstetidens massa till jobbets cirkel för alla uppstartens
        anställda, så undantaget behövs inte."""
        if not hasattr(self, "circles"):
            return
        j = self.circles.add(idx, str(onet_code), float(x), float(y), float(r_o) ** 2, 0.0,
                             rho2_home=float(r_o) ** 2)
        self._active_slot[idx] = j

    def clear_active_occupation(self, idx):
        if hasattr(self, "_active_slot"):
            self._active_slot[idx] = -1

    def evolve_competence(self, dt_years):
        if not hasattr(self, "circles"):
            return
        self.circles.evolve(dt_years, self._active_slot, self.competence_params())
        self._write_competence_summary()

    def job_index(self):
        """job_id -> positionsindex. Uppslag via boolesk jämförelse över hela
        tabellen kostade 825 mikrosekunder per anrop; en dict kostar 33."""
        n = len(self.jobs)
        if getattr(self, "_ji_n", None) != n:
            self._ji = {j: i for i, j in enumerate(self.jobs["job_id"].to_numpy())}
            self._ji_n = n
        return self._ji

    def vacant_mask(self):
        """Boolesk vy över lediga, aktiva positioner, underhållen inkrementellt.

        Att räkna om masken ur individual_id kostade 392 mikrosekunder per
        sökning, eftersom isna på en strängkolumn är dyr: 6.7 av 33 sekunder i
        en Mora-körning låg i _isna_string_dtype. Cachad array kostar 3.
        Masken byggs om när tabellen ändrar längd och uppdateras punktvis av
        set_job_filled och set_job_inactive.
        """
        n = len(self.jobs)
        if getattr(self, "_vm_n", None) != n:
            filled = self.jobs["individual_id"].notna().to_numpy()
            act = (self.jobs["active"].to_numpy(dtype=bool)
                   if "active" in self.jobs.columns else np.ones(n, dtype=bool))
            pend = (self.jobs["pending"].to_numpy(dtype=bool)
                    if "pending" in self.jobs.columns else np.zeros(n, dtype=bool))
            # Externa jobb (utpendlarnas, docs/omgivning.md) är aldrig vakanser
            # i regionen.
            ext = (self.jobs["extern"].fillna(False).to_numpy(dtype=bool)
                   if "extern" in self.jobs.columns else np.zeros(n, dtype=bool))
            self._vm = (~filled) & act & (~pend) & (~ext)
            self._vm_n = n
        return self._vm

    def set_job_filled(self, job_id, filled, t_now=None):
        """Håller vakansmasken i synk när en position tillsätts eller frigörs.

        Går via vacant_mask(), som bygger om masken när tabellen ändrat längd.
        Direkt åtkomst till _vm gav IndexError när en nypostad position
        förstördes innan någon sökning hunnit utlösa ombyggnaden.

        En frigjord position kräver tiden. Fram till 0086 stämplades
        vacant_since med self.current_time, som sattes till 0 i __init__ och
        aldrig flyttades: den hörde till den döda tick()-slingan, inte till
        händelsekön. Varje frigjord position fick därför ålder lika med
        klockan vid tillsättningen, och medianåldern blev 1 134 dagar."""
        if not filled and t_now is None:
            raise TypeError("set_job_filled(..., False) kräver t_now: "
                            "vacant_since stämplas med händelsens tid")
        pos = self.job_index().get(job_id)
        if pos is not None and not filled and "extern" in self.jobs.columns \
                and bool(self.jobs["extern"].iat[pos]):
            # ETT EXTERNT JOBB UPPHÖR NÄR DET LÄMNAS. Det har ingen arbetsgivare
            # som kan annonsera det igen, och en ledig position utanför regionen
            # är ingen vakans här (docs/omgivning.md, O4). Alla vägar som
            # lämnar ett jobb går hit.
            self.jobs.iat[pos, self.jobs.columns.get_loc("active")] = False
            if "destroyed_time" in self.jobs.columns:
                self.jobs.iat[pos, self.jobs.columns.get_loc("destroyed_time")] = float(t_now)
            vm = self.vacant_mask()
            if pos < vm.size:
                vm[pos] = False
            return
        if pos is not None:
            vm = self.vacant_mask()
            if pos < vm.size:
                vm[pos] = not filled
            if not filled and 'vacant_since' in self.jobs.columns:
                self.jobs.iat[pos, self.jobs.columns.get_loc('vacant_since')] = \
                    float(t_now)
        if pos is not None and "pending" in self.jobs.columns:
            # Rensas i båda riktningarna: rekryteringen är avslutad antingen
            # genom tillträde eller genom att positionen frigjorts.
            self.jobs.iat[pos, self.jobs.columns.get_loc("pending")] = False

    # ---- ansökningar ------------------------------------------------------
    def file_application(self, job_id, idx, t_now, **bud):
        """Lägger en ansökan och öppnar annonsen om den inte redan är öppen.

        Fönstret schemalägger EN close_vacancy per annons, vid första
        ansökan. En vakans utan sökande får därför ingen händelse alls, vilket
        är både billigt och rätt: den står kvar och kan hittas igen.

        Under fönstret byter ingenting tillstånd -- arbetaren är arbetslös och
        positionen ledig -- så bokföringsidentiteten U = L - J + V är oberörd.
        """
        if not hasattr(self, "applications"):
            self.applications = {}
        self.applicant_counts()      # materialisera FÖRE mutationen, annars
                                     # räknas den nya raden två gånger
        first = job_id not in self.applications
        kö = self.applications.setdefault(job_id, [])
        if any(a["idx"] == idx for a in kö):
            return False                      # redan sökt, ingen dubblett
        kö.append(dict(idx=idx, t=float(t_now), **bud))
        self._bump_applicant_count(job_id, 1.0)
        if first:
            days = float(self.cfg_reader.config.get("simulation", {})
                         .get("application_window_days", 40.0))
            self._push_event({"time": float(t_now) + days, "agent_id": idx,
                              "event_type": "close_vacancy",
                              "params": {"job_id": job_id}})
            # VÄNTAN PÅ FÖRSTA SÖKANDEN (0102). Vakansens ålder vid tillträdet
            # är 80 dagar och fönstret 40 av dem; resten är väntan på att någon
            # alls ska söka plus tiden fram till tillträdet. Den första posten
            # loggas här, vid annonsens öppning, eftersom den inte går att
            # räkna ut i efterhand: en vakans utan sökande har ingen händelse.
            pos = self.job_index().get(job_id)
            if pos is not None and 'vacant_since' in self.jobs.columns:
                vs = float(self.jobs.iat[pos, self.jobs.columns.get_loc('vacant_since')])
                rad = self.jobs.iloc[pos]
                extra = {"event_detail": "advert_opened", "job_id": job_id,
                         "wait_first_applicant_days": round(float(t_now) - vs, 1)}
                # Vakansens EGENSKAPER på samma rad (0107): utan dem går
                # väntetiden inte att ställa mot kravnivån, och frågan om
                # svansen är tunnhet eller artefakt kan inte avgöras.
                for kol, namn in (('r_req', 'r_req'), ('onet_code', 'onet'),
                                  ('municipal_code', 'municipality'),
                                  ('employer_size', 'employer_size')):
                    if kol in self.jobs.columns:
                        v = rad.get(kol)
                        if v is not None and not (isinstance(v, float) and np.isnan(v)):
                            extra[namn] = round(float(v), 4) if namn in ('r_req',) else str(v)
                self.event_logger.log_event(
                    self, {"time": float(t_now), "agent_id": None,
                           "event_type": "open_advert"}, extra=extra)
        return True

    def applicant_counts(self):
        """Antal liggande ansökningar per jobbposition, underhållen array.

        Behövs vid VARJE sökning, så den byggs inte om per anrop: en array
        över femtontusen jobb allokerad hundratusentals gånger är ren
        allokeringsvärme. Samma mönster som vacant_mask -- byggs om när
        tabellen ändrar längd, uppdateras punktvis av file_application och
        close_application_window.
        """
        n = len(self.jobs)
        if getattr(self, "_ac_n", None) != n:
            self._ac = np.zeros(n, dtype=float)
            self._ac_n = n
            pos_of = self.job_index()
            for jid, kö in getattr(self, "applications", {}).items():
                pos = pos_of.get(jid)
                if pos is not None and pos < n:
                    self._ac[pos] = len(kö)
        return self._ac

    def _bump_applicant_count(self, job_id, delta):
        ac = self.applicant_counts()
        pos = self.job_index().get(job_id)
        if pos is not None and pos < ac.size:
            ac[pos] = max(0.0, ac[pos] + delta)

    def close_application_window(self, job_id):
        if not hasattr(self, "applications"):
            self.applications = {}
        self.applicant_counts()      # samma skäl som i file_application
        kö = self.applications.pop(job_id, [])
        if kö:
            self._bump_applicant_count(job_id, -float(len(kö)))
        return kö

    def n_open_applications(self):
        return sum(len(v) for v in getattr(self, "applications", {}).values())

    def set_job_pending(self, job_id):
        """Positionen är utlovad men inte tillträdd: ingen annan kan söka den,
        men den räknas fortfarande som en öppen vakans."""
        pos = self.job_index().get(job_id)
        if pos is None:
            return
        if "pending" in self.jobs.columns:
            self.jobs.iat[pos, self.jobs.columns.get_loc("pending")] = True
        vm = self.vacant_mask()
        if pos < vm.size:
            vm[pos] = False

    def set_job_inactive(self, job_id):
        pos = self.job_index().get(job_id)
        if pos is not None:
            vm = self.vacant_mask()
            if pos < vm.size:
                vm[pos] = False

    def job_arrays(self):
        """Cachad numpy-vy av jobbtabellen, byggs om när tabellen ändrar längd
        (dvs. när vakanser postas). Attributen x_occ, y_occ, r_o, wage, x, y
        ändras inte för ett befintligt jobb."""
        from core.occupations.utils import build_job_arrays
        n = len(self.jobs)
        if getattr(self, "_ja_n", None) != n:
            self._ja = build_job_arrays(self.jobs)
            self._ja_n = n
        return self._ja

    # match_individuals_to_jobs och update_after_matching utgick i 0069.
    # De körde interleaved_multilevel_batch_matching / global_greedy_matching,
    # en tidigare version av samma modell: samma överskott, samma dragning på
    # passform, samma sortering på S -- men utan kön i överskottet (0057),
    # arbetsgivarens urval (0055), kravgrinden (0049) och loneformeln
    # w = Pi_j * p**theta med arbetsgivareffekt (0061, 0063). Nio tusen
    # matchningar, alltså större delen av beståndet i flera år, var därför
    # gjorda under en modell vi inte längre tror på.
    #
    # Dessutom partitionerade den GEOGRAFISKT, DeSO -> kommun -> globalt.
    # Individer i samma bostadsområde liknar varandra i uppgiftsrummet, så den
    # som råkade komma tidigt i deso_codes-ordningen tog de bästa jobben i hela
    # kommunen: en gradient efter körordning, permanent, i en modell där
    # geografi är glesbygdspapprets förklaringsvariabel.
    #
    # Uppstarten ligger nu i core.matching_core.bootstrap_matching och anropar
    # samma funktioner som händelsehanterarna. _seed_wages_for_matched (0068)
    # utgår med den: startlönen kommer ur negotiated_wage som för alla andra.

    def employer_training_prob(self, n_employees):
        tr_cfg = self.cfg_reader.config.get('defaults', {}).get('employer', {}).get('training_prob_by_size', {})
        if n_employees < 10:
            return tr_cfg.get('small', 0.05)
        elif n_employees < 100:
            return tr_cfg.get('medium', 0.15)
        else:
            return tr_cfg.get('large', 0.40)
        

# Importera event handlers sist!
from core.event_handlers import *
