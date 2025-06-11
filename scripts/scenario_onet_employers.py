import sys
import os
import matplotlib.pyplot as plt
import numpy as np
import uuid

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.occupational_profiles import transform_onet_skills_scaled, select_representative_occupations
from core.agents import Employer, Job
from core.plotting.occupational import plot_occupation_space

# 1. Ladda transformerade O*NET-data (hela datasettet)
all_occupations_df = transform_onet_skills_scaled(n_clusters=50)

# 2. Välj representativa yrken per kluster
df = select_representative_occupations(all_occupations_df)

# 3. Skapa arbetsgivare baserat på varje occupation-kluster
employers = []
for i, row in df.iterrows():
    emp_id = str(uuid.uuid4())
    position = (np.random.uniform(0, 100), np.random.uniform(0, 100))
    segment = row['Xi']
    size = np.random.randint(3, 10)

    employer = Employer(
        id=emp_id,
        position=position,
        segment=segment,
        size=size
    )

    for _ in range(size):
        job = Job(
            id=str(uuid.uuid4()),
            chi=row['Chi'] + np.random.normal(0, 0.2),
            xi=row['Xi'] + np.random.normal(0, 0.1),
            position=position,
            employer_id=emp_id
        )
        employer.jobs.append(job)

    employers.append(employer)

# 4. Visualisera occupation space för de representativa yrkena
fig, ax = plot_occupation_space(df, bubble_scale=1.5, labels=True)
fig.suptitle("Occupation Space of Employers (Representative O*NET Occupations)")
fig.tight_layout()
plt.show()
