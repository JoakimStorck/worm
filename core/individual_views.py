"""Individtabellen som kolumnvyer (0110).

Profilen efter 0108: 25 av 64 sekunder gick till pandas radaccess --
1.3 miljoner .at[]-läsningar à 8-12 us och 127 000 .loc[idx]-Series à
60 us. En läsning ur en numpy-array kostar 0.1 us.

Vyerna är df[kolumn].to_numpy(): de aliasar tabellens minne, så en
skrivning med .at[] syns i vyn utan att något behöver synkas. Det håller så
länge pandas inte kopierar blocket, vilket den gör vid tilldelning av en hel
kolumn (prepare, tester) och kan göra vid Copy-on-Write om en annan Series
refererar blocket när .at[] skriver. Därför: vyerna byggs om i prepare() och
vid varje månadsskifte, och VID MÅNADSSKIFTET VERIFIERAS de gamla vyerna mot
tabellen innan de byts. Har de tappat kontakten kastas ett fel -- ingen tyst
avvikelse som får leva vidare i ett år av körning. Att frame byts (tester gör
det) fångas på objektets id och längd.

Läsningar går genom get_ind()/ind_row(); skrivningar går som förut genom
.at[], som skriver på plats. En mixin, så att också testernas stubbar kan
bära den.
"""
import numpy as np
import pandas as pd


class IndividualViews:
    IND_VIEW_COLUMNS = ('status', 'job_id', 'w_res', 'w_neg', 'accepted_job_id',
                        'notice_job_id', 'individual_id', 'q_last', 'x_occ', 'y_occ',
                        'x', 'y', 'r_i', 'propensity_start_education', 'next_search_time',
                        'last_onet_code', 'propensity_internal_training',
                        'propensity_internal_job_change', 'municipal_code', 'extern',
                        # anspråkets tillstånd, läst vid varje sökning (_tal)
                        'unemployed_since', 'w_last', 'pi_o', 'w_rel_med', 'w_rel_sd',
                        'p_claim0', 'w_res_time', 'last_education_draw')
    _SAKNAS = object()

    def refresh_ind(self, verify=False):
        df = self.individuals
        if verify and getattr(self, '_iv', None) and self._iv_id == id(df) \
                and self._iv_n == len(df):
            for kol, vy in self._iv.items():
                if kol not in df.columns:
                    continue
                nu = df[kol].to_numpy()
                if nu.dtype.kind == 'f' and vy.dtype.kind == 'f':
                    lika = np.array_equal(nu, vy, equal_nan=True)
                else:
                    lika = all((a is b) or (a == b) or (pd.isna(a) and pd.isna(b))
                               for a, b in zip(nu, vy))
                if not lika:
                    raise RuntimeError(
                        f"individtabellens kolumnvy '{kol}' har tappat kontakten med "
                        "tabellen: en hel kolumn har tilldelats eller pandas har "
                        "kopierat blocket. Anropa refresh_ind() efter kolumntilldelning.")
        self._iv = {k: df[k].to_numpy() for k in self.IND_VIEW_COLUMNS if k in df.columns}
        self._iv_id, self._iv_n = id(df), len(df)
        ix = df.index
        if isinstance(ix, pd.RangeIndex) and ix.start == 0 and ix.step == 1:
            self._iv_pos = None
        else:
            self._iv_pos = {k: i for i, k in enumerate(ix)}

    def _iv_ready(self):
        df = self.individuals
        if getattr(self, '_iv', None) is None or self._iv_id != id(df) or self._iv_n != len(df):
            self.refresh_ind()

    def get_ind(self, idx, col, default=_SAKNAS):
        """Ett fält ur individtabellen, ur kolumnvyn.

        Saknas kolumnen kastas KeyError precis som .at[] gjorde -- ingen tyst
        None -- om inte anroparen uttryckligen gett ett default."""
        self._iv_ready()
        vy = self._iv.get(col)
        if vy is None:
            if col in self.individuals.columns:
                return self.individuals.at[idx, col]
            if default is IndividualViews._SAKNAS:
                raise KeyError(col)
            return default
        pos = idx if self._iv_pos is None else self._iv_pos[idx]
        return vy[pos]

    def ind_row(self, idx, cols=None):
        """Individens hot-fält som dict -- ersätter individuals.loc[idx], som
        bygger en Series över alla kolumner för att några få ska läsas."""
        self._iv_ready()
        pos = idx if self._iv_pos is None else self._iv_pos[idx]
        cols = cols or self._iv.keys()
        return {k: self._iv[k][pos] for k in cols if k in self._iv}
