import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

# Ladda tabell med occupation space och O*NET Education/Experience
occ = pd.read_csv('data/onet_occupation_space-db250628.csv')
onet = pd.read_csv('onet_data/education_training_experience.csv')  # O*NET-tabellen

# A. Utbildningsnivå per yrke
edu = onet[(onet['Element Name'] == 'Required Level of Education') & (onet['Scale ID'] == 'RL')]
edu['RL'] = edu['Category'].astype(int)
edu_grouped = edu.groupby('O*NET-SOC Code').apply(lambda g: (g['Data Value'] * g['RL']).sum() / g['Data Value'].sum())
edu_grouped = edu_grouped.rename('exp_education').reset_index()

# B. Erfarenhet per yrke
exp = onet[(onet['Element Name'] == 'Related Work Experience') & (onet['Scale ID'] == 'RW')]
exp['RW'] = exp['Category'].astype(int)
exp_grouped = exp.groupby('O*NET-SOC Code').apply(lambda g: (g['Data Value'] * g['RW']).sum() / g['Data Value'].sum())
exp_grouped = exp_grouped.rename('exp_experience').reset_index()

# Mappa in till din occupation space-tabell
occ = occ.merge(edu_grouped, left_on='onet_code', right_on='O*NET-SOC Code', how='left')
occ = occ.merge(exp_grouped, left_on='onet_code', right_on='O*NET-SOC Code', how='left', suffixes=('', '_exp'))

# Kolla korrelationer och visualisera!
print(occ[['chi', 'h', 'exp_education', 'exp_experience']].corr())
