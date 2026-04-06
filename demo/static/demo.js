// ============================================
// AZURE ARCHITECTURE FACTORY DEMO SCRIPT
// ============================================

const API_BASE = '/api';

function delay(ms) {
    return new Promise(resolve => window.setTimeout(resolve, ms));
}

async function fetchJsonWithRetry(url, options = {}, retryCount = 1) {
    let lastError = null;

    for (let attempt = 0; attempt <= retryCount; attempt += 1) {
        try {
            const response = await fetch(url, {
                cache: 'no-store',
                credentials: 'same-origin',
                ...options,
            });

            const rawText = await response.text();
            let data = null;

            try {
                data = rawText ? JSON.parse(rawText) : null;
            } catch {
                throw new Error(`Server returned a non-JSON response (${response.status}).`);
            }

            if (!response.ok) {
                throw new Error(data?.message || `Request failed with HTTP ${response.status}.`);
            }

            return data;
        } catch (error) {
            lastError = error;
            if (attempt < retryCount) {
                await delay(600 * (attempt + 1));
                continue;
            }
        }
    }

    throw lastError || new Error('Request failed.');
}

async function refreshProjectLinkStatus(showToast = false) {
    try {
        const response = await fetch(`${API_BASE}/project-link-status`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        for (const project of data.projects || []) {
            const badge = document.getElementById(`project-status-${project.id}`);
            const link = document.getElementById(`project-link-${project.id}`);

            if (badge) {
                badge.classList.remove('project-runtime-pending', 'project-runtime-running', 'project-runtime-offline');
                badge.classList.add(project.running ? 'project-runtime-running' : 'project-runtime-offline');
                badge.textContent = project.running
                    ? `Running${project.status_code ? ` (${project.status_code})` : ''}`
                    : 'Offline';
            }

            if (link) {
                link.classList.toggle('is-disabled', !project.running);
                link.setAttribute('aria-disabled', String(!project.running));
                link.textContent = project.running ? project.cta : 'Offline';
                if (!project.running) {
                    link.setAttribute('tabindex', '-1');
                } else {
                    link.removeAttribute('tabindex');
                }
            }
        }

        if (showToast) {
            showNotification('Project link statuses refreshed.', 'success');
        }
    } catch (error) {
        console.error('Error refreshing project link status:', error);
        if (showToast) {
            showNotification('Failed to refresh project link statuses.', 'error');
        }
    }
}

function renderFactoryAssessment(summary) {
    const assessmentEl = document.getElementById('factory-assessment');
    if (!assessmentEl) {
        return;
    }

    assessmentEl.innerHTML = `
        <div class="rich-item">
            <strong>Assessment</strong>
            <p>${summary.assessment}</p>
        </div>
        <div class="rich-item">
            <strong>Strongest Evidence</strong>
            <p>${summary.strongest_evidence}</p>
        </div>
        <div class="rich-item">
            <strong>Coverage Snapshot</strong>
            <p>${summary.diagram_count} projects with diagrams, ${summary.source_count} with source code, ${summary.docs_count} with project docs, ${summary.tests_count} with tests, ${summary.infra_count} with infrastructure.</p>
        </div>
    `;
}

function renderFactoryProjects(projects) {
    const projectMetricsEl = document.getElementById('factory-project-metrics');
    if (!projectMetricsEl) {
        return;
    }

    projectMetricsEl.innerHTML = projects.map(project => `
        <div class="rich-item">
            <strong>${project.name}</strong>
            <p>${project.description}</p>
            <p><span class="pill-inline">${project.kind}</span><span class="pill-inline">${project.path}</span></p>
            <p>${project.evidence.join(' • ')}</p>
        </div>
    `).join('');
}

function renderValidationResults(data, showToast = false) {
    const summaryEl = document.getElementById('factory-validation-summary');
    const outputEl = document.getElementById('factory-validation-output');

    if (summaryEl) {
        summaryEl.innerHTML = (data.suites || []).map(suite => `
            <div class="rich-item">
                <strong>${suite.project}</strong>
                <p>Status: ${suite.status}</p>
                <p>${suite.summary || suite.message || 'No summary available.'}</p>
            </div>
        `).join('');
    }

    if (outputEl) {
        outputEl.textContent = (data.suites || [])
            .map(suite => `${suite.project}\n${suite.output || suite.message || 'No output available.'}`)
            .join('\n\n------------------------------\n\n');
    }

    if (showToast) {
        showNotification(
            data.status === 'success' ? 'Validation suite completed successfully.' : 'Validation suite completed with failures.',
            data.status === 'success' ? 'success' : 'error'
        );
    }
}

async function loadFactoryReadiness(showToast = false) {
    const statusEl = document.getElementById('live-status');
    const projectCountEl = document.getElementById('live-project-count');
    const fullLifecycleCountEl = document.getElementById('live-full-lifecycle-count');
    const productionCountEl = document.getElementById('live-production-count');
    const testableCountEl = document.getElementById('live-testable-count');

    if (!statusEl) {
        return;
    }

    statusEl.textContent = 'Loading readiness evidence...';

    try {
        const response = await fetch(`${API_BASE}/factory-readiness`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        const summary = data.summary || {};

        projectCountEl.textContent = summary.project_count ?? 0;
        fullLifecycleCountEl.textContent = summary.full_lifecycle_count ?? 0;
        productionCountEl.textContent = summary.production_like_count ?? 0;
        testableCountEl.textContent = summary.testable_project_count ?? 0;

        renderFactoryAssessment(summary);
        renderFactoryProjects(data.projects || []);

        statusEl.textContent = data.updated_at
            ? `Readiness evidence refreshed: ${new Date(data.updated_at).toLocaleString()}`
            : 'Readiness evidence loaded.';

        if (showToast) {
            showNotification('Factory readiness evidence refreshed.', 'success');
        }
    } catch (error) {
        console.error('Error loading factory readiness:', error);
        statusEl.textContent = 'Failed to load readiness evidence.';
        if (showToast) {
            showNotification('Failed to refresh readiness evidence.', 'error');
        }
    }
}

async function runFactoryValidation() {
    const statusEl = document.getElementById('live-status');
    const runBtn = document.getElementById('run-readiness-btn');
    const originalText = runBtn ? runBtn.textContent : 'Run Validation Suite';

    if (runBtn) {
        runBtn.disabled = true;
        runBtn.textContent = 'Running...';
    }

    if (statusEl) {
        statusEl.textContent = 'Running representative validation suites...';
    }

    try {
        const response = await fetch(`${API_BASE}/run-factory-validation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || 'Validation run failed');
        }

        renderValidationResults(data, true);
        await loadFactoryReadiness();
    } catch (error) {
        console.error('Error running factory validation:', error);
        if (statusEl) {
            statusEl.textContent = `Validation run failed: ${error.message}`;
        }
        showNotification('Validation run failed.', 'error');
    } finally {
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.textContent = originalText;
        }
    }
}

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
 * Run the order management platform test suite and display results.
 */
async function runOrderManagementTests() {
    const statusEl = document.getElementById('order-mgmt-status');
    const runBtn = document.getElementById('run-order-mgmt-btn');
    const countsEl = document.getElementById('order-mgmt-counts');
    const detailsEl = document.getElementById('order-mgmt-details');
    const testList = document.getElementById('order-test-list');
    const rawOutput = document.getElementById('order-raw-output');

    if (runBtn) { runBtn.disabled = true; runBtn.textContent = '⏳ Running...'; }
    if (statusEl) { statusEl.textContent = 'Running order management test suite...'; }
    if (countsEl) { countsEl.style.display = 'none'; }
    if (detailsEl) { detailsEl.style.display = 'none'; }
    if (rawOutput) { rawOutput.textContent = 'Waiting for test output...'; }
    if (testList) { testList.innerHTML = ''; }

    try {
        const data = await fetchJsonWithRetry(`/api/run-order-management?ts=${Date.now()}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache',
            },
            body: '{}',
        }, 1);

        if (data.status === 'error') {
            throw new Error(data.message || 'Unknown error');
        }

        // Update counters
        document.getElementById('order-passed-count').textContent = data.passed ?? 0;
        document.getElementById('order-failed-count').textContent = data.failed ?? 0;
        document.getElementById('order-total-count').textContent = data.total ?? 0;
        document.getElementById('order-summary-time').textContent = data.summary || '-';

        // Build test result list
        if (testList) {
            testList.innerHTML = (data.tests || []).map(t => {
                const cls = t.result === 'PASSED' ? 'test-passed' : (t.result === 'FAILED' ? 'test-failed' : 'test-error');
                const badgeCls = t.result === 'PASSED' ? 'badge-passed' : (t.result === 'FAILED' ? 'badge-failed' : 'badge-error');
                return `<li class="${cls}"><span class="test-badge ${badgeCls}">${t.result}</span>${t.name}</li>`;
            }).join('') || '<li>No test results parsed.</li>';
        }

        if (rawOutput) { rawOutput.textContent = data.output || '(no output)'; }

        if (countsEl) { countsEl.style.display = 'grid'; }
        if (detailsEl) { detailsEl.style.display = 'grid'; }

        const icon = data.status === 'success' ? '✅' : '❌';
        if (statusEl) {
            statusEl.textContent = `${icon} ${data.summary || 'Tests complete'} — ran at ${new Date(data.ran_at).toLocaleTimeString()}`;
        }

        showNotification(
            data.status === 'success' ? `All ${data.passed} tests passed!` : `${data.failed} test(s) failed.`,
            data.status === 'success' ? 'success' : 'error'
        );
    } catch (error) {
        console.error('Error running order management tests:', error);
        if (statusEl) { statusEl.textContent = `Error: ${error.message}`; }
        if (rawOutput) {
            rawOutput.textContent = `The browser request failed before the test result could be rendered.\n\n${error.message}`;
        }
        if (detailsEl) { detailsEl.style.display = 'grid'; }
        showNotification('Order management tests failed to run.', 'error');
    } finally {
        if (runBtn) { runBtn.disabled = false; runBtn.textContent = '▶ Run Tests Now'; }
    }
}

/**
 * Load async data on page load
 */
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await refreshProjectLinkStatus();
        await loadFactoryReadiness();
        window.setInterval(() => {
            refreshProjectLinkStatus(false);
        }, 15000);
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
