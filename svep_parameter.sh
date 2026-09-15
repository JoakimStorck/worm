#!/usr/bin/env bash
# svep_parameter.sh -- svep en simulation-parameter utan att smutsa trädet.
#
# kor_0077.sh vägrar starta på ocommittade ändringar, eftersom körningen då
# inte är återskapbar. Att sed:a i scenarios/_simulation_defaults.yml gör
# precis det, och ett svep skrivet så kör aldrig något -- det såg ut att
# fungera men producerade tre identiska utskrifter från den förra körningen.
#
# Här skrivs i stället en OSPÅRAD scenariofil per värde, som ärver från
# grundscenariot och bara skriver över parametern. Ospårade filer räknas inte
# som ocommittade ändringar (se _git_dirty i scenario_runner), så körskriptet
# släpper igenom dem -- och run_meta.json noterar dem ändå under git_untracked,
# så härkomsten är ärlig.
#
#   bash svep_parameter.sh commute_decay_km "40 25 15" ovansiljan_3_kommuner
#
set -euo pipefail

PARAM="${1:?ange parameternamn, t.ex. commute_decay_km}"
VARDEN="${2:?ange värden inom citattecken, t.ex. \"40 25 15\"}"
GRUND="${3:-ovansiljan_3_kommuner}"
FRO="${4:-1}"

for v in $VARDEN; do
  namn="_svep_${PARAM}_${v}"
  cat > "scenarios/${namn}.yml" <<YAML
# Genererad av svep_parameter.sh. Ospårad med avsikt: se skriptets huvud.
extends: ${GRUND}.yml
scenario_name: "${GRUND} ${PARAM}=${v}"
simulation:
  ${PARAM}: ${v}
  logfile_path: output/${namn}.log
YAML
  echo "=== ${PARAM} = ${v} ==="
  SCENARIO="scenarios/${namn}.yml" bash kor_0077.sh "$FRO"
  python scripts/diagnose_commuting.py | sed -n '/Flöden över/,/^$/p'
  python -c "
import pandas as pd, glob
d = sorted(glob.glob('output/run_*'))[-1]
i = pd.read_csv(f'{d}/final_state_individuals.csv')
i['kom'] = i.individual_id.astype(str).str.split('_i').str[0]
t = i.groupby('kom').status.value_counts().unstack(fill_value=0)
u = (100*t.unemployed/(t.employed+t.unemployed)).round(1)
print('arbetslöshet (andel av arbetskraften):', u.to_dict())
print('SCB 2023: 2034 Orsa 3.51, 2039 Älvdalen 3.17, 2062 Mora 2.35')
"
done
