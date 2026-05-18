/* Architecture Page - Component Details */

const API_BASE = 'http://localhost:5001';

document.addEventListener('DOMContentLoaded', () => {
    loadArchitectureComponents();
});

async function loadArchitectureComponents() {
    try {
        const response = await fetch(`${API_BASE}/api/architecture`);
        const architecture = await response.json();
        
        const grid = document.getElementById('components-grid');
        if (!grid) return;

        grid.innerHTML = Object.entries(architecture.services).map(([key, service]) => {
            const services = service.services || [];
            const benefits = service.benefits || [];
            
            return `
                <div class="component-card">
                    <div class="component-icon">${service.icon}</div>
                    <h3>${service.name}</h3>
                    <p class="component-desc">${service.description}</p>
                    
                    ${services.length > 0 ? `
                        <h4 style="color: #0078D4; margin-top: 1rem; margin-bottom: 0.5rem; font-size: 0.95rem;">Services:</h4>
                        <ul class="component-services">
                            ${services.map(s => `<li>${s}</li>`).join('')}
                        </ul>
                    ` : ''}
                    
                    <div class="component-benefits">
                        ${benefits.map(benefit => `
                            <span class="benefit-badge">${benefit}</span>
                        `).join('')}
                    </div>
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('Error loading architecture:', error);
    }
}
