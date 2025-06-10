import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


import pandas as pd
import matplotlib.pyplot as plt

# Filnamn till loggfilen (byt ut om annan)
LOGFILE = 'output/falun_baseline.log'

# Tomma listor för statistik
times = []
employed = []
unemployed = []
unmatched_jobs = []

with open(LOGFILE, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('#') or not line:
            continue  # hoppa över tomma eller kommenterade rader

        parts = [p.strip() for p in line.split(',')]

        # Kolla på aggregerade statusrader: new_year och new_month
        if len(parts) >= 3 and (parts[1] == 'new_year' or parts[1] == 'new_month'):
            # Förväntat format: tid, new_year, år, employed X, unemployed Y, matched Z, unmatched_jobs W
            t = float(parts[0])
            # Hämta alla poster i raden som är på formen 'employed NNN'
            stat_dict = {}
            for item in parts:
                if ' ' in item:
                    key, value = item.split()
                    stat_dict[key] = int(value)
            # Samla data om finns
            if 'employed' in stat_dict and 'unemployed' in stat_dict and 'unmatched_jobs' in stat_dict:
                times.append(t)
                employed.append(stat_dict['employed'])
                unemployed.append(stat_dict['unemployed'])
                unmatched_jobs.append(stat_dict['unmatched_jobs'])

# Lägg i DataFrame för smidigare hantering
df = pd.DataFrame({
    'time': times,
    'employed': employed,
    'unemployed': unemployed,
    'unmatched_jobs': unmatched_jobs
})

print(df.head())
print(df.tail())

# Enkel plott för översikt
plt.figure(figsize=(10, 5))
plt.plot(df['time'], df['employed'], label='Employed')
plt.plot(df['time'], df['unemployed'], label='Unemployed')
plt.plot(df['time'], df['unmatched_jobs'], label='Unmatched Jobs')
plt.xlabel('Time (days)')
plt.ylabel('Number of individuals/jobs')
plt.legend()
plt.title('Labor Market Status Over Time')
plt.tight_layout()
plt.show()
