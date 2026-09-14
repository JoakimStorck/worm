"""
core/scenario_result.py
-----------------------
Körningens tre tabeller och dess händelsekö, hållna ihop under körningen.
Skapas i scenario_runner steg 3 och lämnas vidare till World.

Klassen bar tidigare också get_indiv_source/get_job_source, som byggde
bokeh-ColumnDataSource, och from_run, som läste en avslutad körning tillbaka
in i en ReplayController. Båda hörde till den gamla Bokeh-appen och togs bort
när den lades i attic/ -- from_run dessutom för att den läste final_state_* och
kallade resultatet ett starttillstånd. Modulens load_initial_state och
restore_geometry gick samma väg: ingen läste dem, och load_initial_state läste
eventlog.csv med pd.read_csv trots att loggen är rader av nyckel-värde-par med
varierande antal fält -- core/analysis/eventlog.py finns för att den tolkningen
ska göras på ett ställe.

Det viktiga med borttagningen är inte raderna utan importen: `from bokeh.models
import ColumnDataSource` låg på toppnivå här, och scenario_runner importerar
den här modulen. Bokeh var därmed ett hårt krav för varje simulering, och
tests/test_job_flows.py::test_dirty_flag_ignores_untracked_files kunde inte
köras utan ett installerat plottbibliotek.
"""


class ScenarioResult:
    def __init__(self, individuals=None, jobs=None, employers=None, events=None, outdir=None):
        self.individuals = individuals
        self.jobs = jobs
        self.employers = employers
        self.events = events
        self.outdir = outdir

    def get_individuals(self, filter_func=None):
        df = self.individuals
        if filter_func:
            df = df[df.apply(filter_func, axis=1)]
        return df

    def get_jobs(self, filter_func=None):
        df = self.jobs
        if filter_func:
            df = df[df.apply(filter_func, axis=1)]
        return df

    def get_employers(self):
        return self.employers

