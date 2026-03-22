# Azure Architecture Factory - Interactive Demo

A modern web-based demonstration of the Azure Architecture Factory platform, featuring interactive scenario selection, workflow visualization, and a comprehensive leadership presentation.

## Features

### 🎯 Interactive Demo Application

- **4 Demo Scenarios**: E-Commerce, Data Pipeline, Microservices, Generative AI
- **6-Phase Workflow Visualization**: See how requirements become production-ready code
- **Project Structure Preview**: View the automatically generated project layout
- **Real-time Simulation**: Simulate deployments and preview endpoints
- **Responsive Design**: Works on desktop, tablet, and mobile

### 📊 Leadership Presentation

A 10-slide executive presentation covering:

1. **The Problem** - Current bottlenecks (4-8 weeks to production)
2. **Business Impact** - Time-to-market and cost implications
3. **The Solution** - Azure Architecture Factory overview
4. **How It Works** - 6-phase automated workflow
5. **Proven Results** - Real metrics (47 deployments, 95.7% success)
6. **Key Benefits** - 90% faster, zero manual handoffs, self-healing IaC
7. **Reference Implementation** - Fabric Medallion pipeline
8. **Use Cases** - Various workload scenarios
9. **Financial Impact** - ROI and cost savings
10. **Next Steps** - Implementation roadmap

## Quick Start

### Installation

```bash
cd demo
pip install -r requirements.txt
python app.py
```

### Access the Demo

- **Demo App**: http://localhost:5000/
- **Leadership Brief**: http://localhost:5000/presentation
- **API Docs**: http://localhost:5000/api/{endpoint}

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

| Key | Action |
|-----|--------|
| `→` or `Space` | Next slide |
| `←` | Previous slide |
| `F` | Toggle fullscreen |
| `Esc` | Exit fullscreen |
| Scroll Up/Down | Navigate slides |

### Mouse & Touch

- Click "Next" / "Previous" buttons
- Swipe left/right on mobile
- Scroll wheel to navigate

## Project Structure

```
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

## Deployment

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

The demo data reflects real Azure Architecture Factory results:

- **47 deployments** completed successfully
- **95.7% success rate** (industry average: 40%)
- **2.3 hours average** time-to-deployment (vs 4-8 weeks manual)
- **12 organizations** using the platform
- **48 teams** actively engaged
- **$2.1M+ cost savings** realized

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+
- Mobile browsers (iOS Safari 14+, Chrome Mobile)

## Troubleshooting

### Port Already in Use

```bash
# Find process on port 5000
lsof -i :5000

# Kill the process or use different port
python app.py --port 5001
```

### Static Files Not Loading

Ensure you're running from the `demo/` directory and Flask can access `templates/` and `static/` folders.

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
1. Check [PROJECT_ROOT]/README.md
2. Review [PROJECT_ROOT]/QUICKSTART.md
3. Open an issue on GitHub
