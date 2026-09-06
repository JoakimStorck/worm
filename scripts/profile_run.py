"""
profile_run.py  (scripts/)
--------------------------
Profilerar en scenariokörning så att optimering kan riktas mot det som
faktiskt kostar tid, i stället för mot det man gissar kostar tid.

    python scripts/profile_run.py scenarios/mora_baseline.yml
    python scripts/profile_run.py scenarios/mora_baseline.yml --sort tottime -n 30

Läs kolumnerna så här: cumtime är tid inklusive anropade funktioner (bra för
att hitta VAR i flödet tiden går), tottime är tid i funktionen själv (bra för
att hitta VAD som ska optimeras). En hög ncalls med låg tottime per anrop är
overhead per anrop -- typiskt DataFrame-kopior eller kategorikonverteringar
som anropas en gång per händelse.
"""
import argparse
import cProfile
import io
import os
import pstats
import sys


def find_repo_root(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, "core")) and os.path.isdir(os.path.join(d, "scenarios")):
            return d
        p = os.path.dirname(d)
        if p == d:
            raise RuntimeError("Hittade ingen repo-rot.")
        d = p


ROOT = find_repo_root(os.path.dirname(__file__))
sys.path.insert(0, ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--sort", default="cumtime", choices=["cumtime", "tottime", "ncalls"])
    ap.add_argument("-n", type=int, default=25, help="antal rader")
    ap.add_argument("--out", default=None, help="spara .prof för snakeviz")
    a = ap.parse_args()

    import core.scenario_runner as r

    pr = cProfile.Profile()
    pr.enable()
    try:
        r.run_and_log_scenario(a.scenario)
    finally:
        pr.disable()

    if a.out:
        pr.dump_stats(a.out)
        print(f"\nSparad: {a.out}   (visualisera med: snakeviz {a.out})")

    buf = io.StringIO()
    st = pstats.Stats(pr, stream=buf).strip_dirs().sort_stats(a.sort)
    st.print_stats(a.n)
    print("\n" + "=" * 78)
    print(f"PROFIL (sorterad på {a.sort})")
    print("=" * 78)
    print(buf.getvalue())

    # Sammanfattning per modul i projektet
    print("=" * 78)
    print("EGEN KOD, samlad per fil")
    print("=" * 78)
    agg = {}
    for (fn, _, _), (_, _, tt, ct, _) in pstats.Stats(pr).stats.items():
        base = os.path.basename(fn)
        if base.endswith(".py") and ("core" in fn or "scripts" in fn):
            t, c = agg.get(base, (0.0, 0.0))
            agg[base] = (t + tt, c + ct)
    for base, (tt, ct) in sorted(agg.items(), key=lambda kv: -kv[1][0])[:15]:
        print(f"  {base:34s} tottime {tt:8.2f} s")


if __name__ == "__main__":
    main()
