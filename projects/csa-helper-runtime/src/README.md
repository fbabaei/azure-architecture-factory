# CSA Helper Runtime — service notes

The `csa-helper` agent runtime is consumed verbatim from
`https://github.com/fbabaei/csa-helper` at Docker build time and mounted
under `/app/csa_helper`. The FastAPI wrapper at `src/api/main.py` imports
`agent_framework.build_team.build_team` and exposes `/ask`, `/health`,
and `/health/ready`. **Do not** modify `build_team.py`; per BRD §7 the
runtime logic and prompts are out of scope for this hosting project.

## Local run (developer)
```pwsh
# Vendor the csa-helper repo locally for development.
git clone https://github.com/fbabaei/csa-helper ../_csa_helper
$env:CSA_HELPER_ROOT = (Resolve-Path ../_csa_helper).Path
$env:AZURE_OPENAI_ENDPOINT = "https://fbfoundrywestus.openai.azure.com/"
$env:AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
$env:AZURE_OPENAI_API_VERSION = "2024-10-21"
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8080
```

## Container build
```pwsh
docker build -t csa-helper-runtime:dev `
  --build-arg CSA_HELPER_REF=main `
  -f Dockerfile .
```
