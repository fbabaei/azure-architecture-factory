# Getting Started with the Azure Architecture Factory Demo

This guide will get you up and running with the interactive demo in 5 minutes.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Quick Start (5 minutes)

### Step 1: Install Dependencies

```powershell
pip install -r .\demo\requirements.txt
```

### Step 2: Start the Demo Server

```powershell
.\scripts\start_portal_from_anywhere.ps1
```

You'll see:

```text
╔════════════════════════════════════════════════════════════════╗
║          Azure Architecture Factory - Demo Application         ║
║                  Starting on http://localhost:5000             ║
╚════════════════════════════════════════════════════════════════╝

Visit:
  🎯 Main demo:       http://localhost:5000/
  📊 Presentation:    http://localhost:5000/presentation
```

### Step 3: Open Your Browser

- **Interactive Demo**: [http://localhost:5000/](http://localhost:5000/)
- **Leadership Brief**: [http://localhost:5000/presentation](http://localhost:5000/presentation)

## What You'll See

### Interactive Demo (`/`)

**Choose a scenario** and watch how the Azure Architecture Factory works:

1. 🛍️ **E-Commerce Platform** - Multi-tenant SaaS (3 hours to deployment)
2. 📊 **Data & Analytics Platform** - Multi-stage analytics delivery (2 hours to deployment)
3. 🔗 **Microservices Architecture** - Containerized services (2.5 hours to deployment)
4. 🤖 **Generative AI Application** - RAG chat app (1.5 hours to deployment)

Click any scenario to see the 6-phase automated workflow.

### Readiness Dashboards

- **Factory Readiness**: Review which sample projects currently include diagrams, source, docs, tests, and infrastructure.
- **BRD Readiness**: Score an incoming BRD and classify it as auto-ready, auto-ready with guardrails, or architect review required.

### Leadership Presentation (`/presentation`)

A 10-slide executive brief covering:

- The problem (4-8 weeks to production)
- The solution (Azure Architecture Factory)
- Measured repository evidence across the tracked sample portfolio
- Evidence-based readiness impact instead of placeholder ROI claims
- ROI and next steps

**Navigate using:**

- Arrow buttons or arrow keys (`←` / `→`)
- Space bar for next slide
- `F` for fullscreen
- Scroll wheel or swipe on mobile

## Demo Features

### Scenario Simulation

- Click any scenario card to see how the platform works
- Watch the 6-phase workflow in action
- See generated project structure
- Preview deployed endpoints

### API Integration

- All API endpoints are documented and accessible
- JSON responses for programmatic access
- Easy integration into your own systems

### Metrics Dashboard

- Repository-level readiness counts derived from current sample artifacts
- Production-like evidence counts across the sample portfolio
- Runnable validation-suite counts surfaced through the portal
- BRD intake scoring with weighted classification

## File Structure

```text
demo/
├── app.py                   # Flask application
├── requirements.txt         # Dependencies
├── templates/
│   ├── index.html          # Demo page
│   └── presentation.html   # Presentation
├── static/
│   ├── styles.css          # Demo styling
│   ├── presentation.css    # Presentation styling
│   ├── demo.js             # Demo logic
│   └── presentation.js     # Presentation logic
└── README.md               # Full documentation
```

## API Endpoints

You can test the API directly:

```bash
# Get all scenarios
curl http://localhost:5000/api/scenarios

# Get workflow details
curl http://localhost:5000/api/workflow

# Get project structure
curl http://localhost:5000/api/project-structure

# Get presentation data
curl http://localhost:5000/api/presentation-data

# Simulate a deployment
curl -X POST http://localhost:5000/api/simulate-deployment \
  -H "Content-Type: application/json" \
  -d '{"scenario": "ecommerce"}'
```

## Customization

### Add a New Scenario

Edit `app.py` and add to `DEMO_SCENARIOS`:

```python
"your_scenario": {
    "name": "Your Scenario Name",
    "description": "What this platform does",
    "industry": "Industry Type",
    "complexity": "Advanced",
    "services": ["Service1", "Service2", "Service3"],
    "timeline": "X hours to deployment"
}
```

Then add a corresponding scenario card in `templates/index.html`.

### Update Presentation Slides

Edit the `@app.route('/api/presentation-data')` section in `app.py`:

```python
"request": {
    "subtitle": "Your slide subtitle",
    "metrics": [
        "Your first metric",
        "Your second metric",
        "Your third metric"
    ]
}
```

## Troubleshooting

### Port 5000 Already In Use

```powershell
netstat -ano | findstr :5000
.\scripts\start_portal_from_anywhere.ps1 -Port 5001
```

### Module Not Found

Make sure you installed dependencies:

```bash
pip install -r requirements.txt
```

### Static Files Not Loading

Start the portal through `.\scripts\start_portal_from_anywhere.ps1` so the app always runs from the correct working directory.

## Next Steps

1. **Explore the Demo** - Click through all 4 scenarios
2. **Watch the Presentation** - Present to your team/leadership
3. **Review the Brief** - Read [LEADERSHIP_PRESENTATION.md](../LEADERSHIP_PRESENTATION.md) for detailed information
4. **Check the Main Repo** - Review [README.md](../README.md) for full project context

## More Information

- 📖 Full [Demo Documentation](README.md)
- 📋 [Leadership Presentation](../LEADERSHIP_PRESENTATION.md) (standalone document)
- 🚀 [Quick Start Guide](../QUICKSTART.md)
- 💼 [Product Requirements](../PRD.md)
- 📊 [Business Requirements](../BRD.md)

## Support

If you encounter issues:

1. Check that Flask is installed: `pip show Flask`
2. Ensure Python 3.8+: `python --version`
3. Check port availability: `netstat -ano | findstr :5000`
4. Review Flask error messages in console

## Advanced: Docker Deployment

```bash
# Build Docker image
docker build -t aaf-demo -f Dockerfile .

# Run container
docker run -p 5000:5000 aaf-demo

# Access at http://localhost:5000
```

Dockerfile:

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
```

## Tips

- Use **full-screen mode** (F key) for presentations to stakeholders
- Press **Space** or **Right Arrow** to advance through presentation slides
- Use **Chrome/Edge** for best cross-browser compatibility
- Mobile browsers work great for demos on the go

Enjoy the demo! 🚀
