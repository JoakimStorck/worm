# core/visualization/selection_sync.py
# Hanterar synkronisering av val mellan arbetsgivare, jobb och individer

def sync_selections(emp_source, job_source, indiv_source):
    # Arbetsgivare → markera tillhörande jobb och individer
    def on_emp_selected(attr, old, new):
        sel = emp_source.selected.indices
        if not sel:
            job_source.selected.indices = []
            indiv_source.selected.indices = []
            return
        emp_ids = [emp_source.data['employer_id'][i] for i in sel]
        job_indices = [i for i, eid in enumerate(job_source.data.get('employer_id', [])) if eid in emp_ids]
        job_source.selected.indices = job_indices
        job_ids = [job_source.data['job_id'][i] for i in job_indices]
        indiv_indices = [i for i, jid in enumerate(indiv_source.data.get('job_id', [])) if jid in job_ids]
        indiv_source.selected.indices = indiv_indices

    # Jobb → markera arbetsgivare och individer
    def on_job_selected(attr, old, new):
        sel = job_source.selected.indices
        if not sel:
            emp_source.selected.indices = []
            indiv_source.selected.indices = []
            return
        job_ids = [job_source.data['job_id'][i] for i in sel]
        emp_ids = [job_source.data['employer_id'][i] for i in sel]
        emp_indices = [i for i, eid in enumerate(emp_source.data.get('employer_id', [])) if eid in emp_ids]
        emp_source.selected.indices = emp_indices
        indiv_indices = [i for i, jid in enumerate(indiv_source.data.get('job_id', [])) if jid in job_ids]
        indiv_source.selected.indices = indiv_indices

    # Individer → markera deras jobb och arbetsgivare
    def on_indiv_selected(attr, old, new):
        sel = indiv_source.selected.indices
        if not sel:
            job_source.selected.indices = []
            emp_source.selected.indices = []
            return
        job_ids = [indiv_source.data.get('job_id', [None])[i] for i in sel]
        job_indices = [i for i, jid in enumerate(job_source.data.get('job_id', [])) if jid in job_ids]
        job_source.selected.indices = job_indices
        emp_ids = [job_source.data.get('employer_id', [None])[i] for i in job_indices]
        emp_indices = [i for i, eid in enumerate(emp_source.data.get('employer_id', [])) if eid in emp_ids]
        emp_source.selected.indices = emp_indices

    emp_source.selected.on_change("indices", on_emp_selected)
    job_source.selected.on_change("indices", on_job_selected)
    indiv_source.selected.on_change("indices", on_indiv_selected)
