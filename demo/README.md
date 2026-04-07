# Azure Architecture Factory - Interactive Demo

A web-based demonstration of the Azure Architecture Factory platform, featuring scenario walkthroughs, repository readiness evidence, and BRD intake scoring.

## Features

### Interactive Demo Application

- **4 Demo Scenarios**: E-Commerce, Data Pipeline, Microservices, Generative AI
- **6-Phase Workflow Visualization**: See how requirements become project structure and deployment assets
- **Factory Readiness Dashboard**: Review evidence across the sample portfolio
- **BRD Readiness Dashboard**: Score new BRDs before sending them into the factory
- **Responsive Design**: Works on desktop, tablet, and mobile

### Leadership Presentation

A 10-slide executive presentation covering:

1. **The Problem** - Current bottlenecks (4-8 weeks to production)
2. **Business Impact** - Time-to-market and cost implications
3. **The Solution** - Azure Architecture Factory overview
4. **How It Works** - 6-phase automated workflow
5. **Proven Results** - Measured repository evidence and tracked sample completeness
6. **Key Benefits** - 90% faster, zero manual handoffs, self-healing IaC
7. **Sample Portfolio** - Multiple example projects and readiness evidence
8. **Use Cases** - Various workload scenarios
9. **Financial Impact** - Evidence-based readiness impact
10. **Next Steps** - Implementation roadmap

## Quick Start

### Installation

```powershell
pip install -r .\demo\requirements.txt
.\scripts\start_portal_from_anywhere.ps1
```

Optional flags:

```powershell
.\scripts\start_portal_from_anywhere.ps1 -NoOpen
.\scripts\start_portal_from_anywhere.ps1 -Port 5001
.\scripts\start_portal_from_anywhere.ps1 -Foreground
```

## Access the Demo

- **Demo App**: <http://localhost:5000/>
- **Factory Readiness**: <http://localhost:5000/factory-readiness>
- **BRD Readiness**: <http://localhost:5000/brd-readiness>
- **Leadership Brief**: <http://localhost:5000/presentation>
- **API Docs**: <http://localhost:5000/api/{endpoint}>

## API Endpoints

### Scenarios

- `GET /api/scenarios` - List all demo scenarios
- `GET /api/scenario/<scenario_id>` - Get scenario details

### Workflow

- `GET /api/workflow` - Get the 6-phase workflow

### Deployment

- `POST /api/simulate-deployment` - Simulate a deployment
- `GET /api/project-structure` - Get generated project structure

### Presentation

- `GET /api/presentation-data` - Get presentation slides (JSON)

## Presentation Navigation

### Keyboard Shortcuts

- `→` or `Space`: Next slide
- `←`: Previous slide
- `F`: Toggle fullscreen
- `Esc`: Exit fullscreen
- Scroll Up/Down: Navigate slides

### Mouse & Touch

- Click "Next" / "Previous" buttons
- Swipe left/right on mobile
- Scroll wheel to navigate

## Project Structure

```text
demo/
├── app.py                          # Flask application
├── requirements.txt                # Python dependencies
├── templates/
│   ├── index.html                  # Main demo page
│   └── presentation.html           # Leadership presentation
└── static/
    ├── styles.css                  # Demo styling
    ├── presentation.css            # Presentation styling
    ├── demo.js                     # Demo interactivity
    └── presentation.js             # Presentation logic
```

## Customization

### Adding New Scenarios

Edit `app.py` and add to `DEMO_SCENARIOS`:

```python
"your_scenario": {
    "name": "Your Scenario",
    "description": "Description here",
    "industry": "Industry",
    "complexity": "Complexity Level",
    "services": ["Service1", "Service2"],
    "timeline": "X hours to deployment"
}
```

### Modifying Presentation Slides

Edit `app.py` in the `@app.route('/api/presentation-data')` function to update slide content.

### Styling

- Demo styles: `static/styles.css`
- Presentation styles: `static/presentation.css`

## Container Deployment

### Docker

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
```

Build and run:

```bash
docker build -t aaf-demo .
docker run -p 5000:5000 aaf-demo
```

### Azure App Service

```bash
az webapp up --resource-group mygroup --name aaf-demo
```

## Performance Metrics

The demo showcases Azure Architecture Factory capabilities:

- **Streamlined deployments** with automation
- **Improved success rates** through standardized patterns
- **Faster time-to-deployment** with infrastructure templates
- **Reduced operational overhead** and complexity
- **Consistent architecture** across projects
- **Cost-effective** infrastructure provisioning

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+
- Mobile browsers (iOS Safari 14+, Chrome Mobile)

## Troubleshooting

### Port Already In Use

```powershell
netstat -ano | findstr :5000
.\scripts\start_portal_from_anywhere.ps1 -Port 5001
```

### Static Files Not Loading

Use the repo-root launcher so the demo always starts with the correct working directory.

### Presentation Not Loading

Check browser console for errors. Ensure API endpoint `/api/presentation-data` is working.

## Future Enhancements

- [ ] PDF export of presentation
- [ ] Speaker notes view
- [ ] Animated workflow visualization
- [ ] Live agent orchestration demo
- [ ] Code snippet viewer
- [ ] Deployment cost calculator
- [ ] Success story gallery
- [ ] FAQ section

## Resources

- [Azure Architecture Factory Main](../)
- [Quick Start Guide](../QUICKSTART.md)
- [Product Requirements](../PRD.md)
- [Business Requirements](../BRD.md)

## License

Same as parent project

## Support

For issues or questions about the demo:

1. Check the repository README.
2. Review [PROJECT_ROOT]/QUICKSTART.md
3. Open an issue on GitHub
