import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


import pandas as pd
ind_id = "2080_i003478"
current_job = None

with open("output/eventlog.log", encoding="utf-8") as f:
    for line in f:
        if f"individual_id {ind_id}" not in line:
            continue
        if "start_job" in line:
            parts = line.split(',')
            # Hitta job_id
            job_id = None
            for p in parts:
                if p.strip().startswith('job_id '):
                    job_id = p.strip().split(' ',1)[1]
            print(f"START_JOB at {parts[0].strip()}: job_id = {job_id} (prev: {current_job})")
            if current_job:
                print("  !!! Redan anställd på jobb:", current_job)
            current_job = job_id
        elif "quit_job" in line:
            print(f"QUIT_JOB at {line.split(',')[0].strip()}: Avslutar {current_job}")
            current_job = None
