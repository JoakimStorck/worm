
from worm.occupational_profiles import transform_onet_skills_scaled
from worm.agents import Employer, Job
from worm.plotting.occupational import plot_occupation_space

import numpy as np
import uuid

# 1. Ladda transformerade O*NET-data
df = transform_onet_skills_scaled(n_clusters=25)

# 2. Skapa arbetsgivare baserat på varje occupation-kluster
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

# 3. Visualisera occupations space
fig, ax = plot_occupation_space(df, bubble_scale=1.5, labels=True)
fig.suptitle("Occupationspace of Employers (O*NET-derived)")
fig.tight_layout()
fig.show()
