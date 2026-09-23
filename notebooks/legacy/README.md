# Optional legacy preparation notebooks

These generic templates predate the final wind forecasting case. They are not
the application, its training pipeline, or evidence of model quality. The random
train/test examples are commented out because they do not enforce chronological
cutoffs or archived-weather availability. Use `forecast.validation` and
[`docs/model-validation.md`](../../docs/model-validation.md) for project validation.

From the repository root, optionally install and launch:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-notebooks.txt
.\start_notebook.ps1
# Alternative generic template:
.\start_notebook.ps1 -Notebook starter
```

The launcher starts only JupyterLab. Use the root `start_hackalem.ps1` for the
dashboard/API and follow the root README for application setup.

Data exploration reads local `data/input/`. The notebooks locate the repository
root even when their kernel starts inside `notebooks/legacy/`. They do not install
packages automatically and do not call OpenAI/NVIDIA unless the optional API
example is explicitly invoked. Local `.env` keys and organizer CSVs must stay out
of Git; clear any notebook outputs before committing after use.
