// ============================================
// AZURE ARCHITECTURE FACTORY DEMO SCRIPT
// ============================================

const API_BASE = '/api';

/**
 * Scroll to demo section
 */
function scrollToDemo() {
    const demoSection = document.getElementById('demo');
    demoSection.scrollIntoView({ behavior: 'smooth' });
}

/**
 * Select a demo scenario
 */
async function selectScenario(scenarioId) {
    const workflow = document.getElementById('workflow');
    const demo = document.getElementById('demo');
    
    // Hide demo, show workflow
    demo.style.display = 'none';
    workflow.style.display = 'block';
    
    // Scroll to workflow
    setTimeout(() => {
        workflow.scrollIntoView({ behavior: 'smooth' });
    }, 100);
    
    // Load workflow data
    try {
        const response = await fetch(`${API_BASE}/workflow`);
        const data = await response.json();
        console.log('Workflow loaded:', data);
    } catch (error) {
        console.error('Error loading workflow:', error);
    }
}

/**
 * Simulate a deployment
 */
async function simulateDeployment() {
    const workflow = document.getElementById('workflow');
    const output = document.getElementById('output');
    
    try {
        // Show loading state
        const btn = event.target;
        const originalText = btn.textContent;
        btn.textContent = 'Deploying...';
        btn.disabled = true;
        
        // Simulate phases with delays
        const phases = [
            { name: 'Project Setup', duration: 100 },
            { name: 'Architecture Diagram', duration: 150 },
            { name: 'Service Scaffolding', duration: 200 },
            { name: 'Infrastructure Generation', duration: 250 },
            { name: 'Production Review', duration: 150 },
            { name: 'Azure Deployment', duration: 300 }
        ];
        
        // Call API to simulate
        const response = await fetch(`${API_BASE}/simulate-deployment`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scenario: 'ecommerce' })
        });
        
        const result = await response.json();
        console.log('Deployment result:', result);
        
        // Show output
        workflow.style.display = 'none';
        output.style.display = 'block';
        output.scrollIntoView({ behavior: 'smooth' });
        
        // Restore button
        btn.textContent = originalText;
        btn.disabled = false;
        
        // Show success notification
        showNotification('Deployment simulation complete!', 'success');
        
    } catch (error) {
        console.error('Error simulating deployment:', error);
        showNotification('Deployment simulation failed', 'error');
        event.target.disabled = false;
    }
}

/**
 * Reset demo
 */
function resetDemo() {
    const demo = document.getElementById('demo');
    const workflow = document.getElementById('workflow');
    const output = document.getElementById('output');
    
    demo.style.display = 'block';
    workflow.style.display = 'none';
    output.style.display = 'none';
    
    demo.scrollIntoView({ behavior: 'smooth' });
}

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'success' ? '#107c10' : '#d83b01'};
        color: white;
        border-radius: 4px;
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

/**
 * Load async data on page load
 */
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // You can pre-load data here if needed
        console.log('Azure Architecture Factory Demo initialized');
    } catch (error) {
        console.error('Error initializing demo:', error);
    }
});

// Add keyboard navigation
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const output = document.getElementById('output');
        if (output.style.display !== 'none') {
            resetDemo();
        }
    }
});
