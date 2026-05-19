# E-Commerce Demo

This sample provides a web-facing e-commerce application generated as part of the Azure Architecture Factory portfolio.

## What this sample includes

- `diagrams/` architecture diagram and notes
- `src/` source pointer for project code organization
- `web/` runnable Flask storefront and API
- `tests/` smoke tests for key API endpoints
- `infra/` infrastructure notes for deployment planning
- `docs/` business and project documentation

## Local run

1. Install dependencies:
   - `pip install -r projects/ecommerce-demo/web/requirements.txt`
2. Start the app:
   - `python projects/ecommerce-demo/web/app.py`
3. Run smoke tests:
   - `python -m unittest discover projects/ecommerce-demo/tests`
