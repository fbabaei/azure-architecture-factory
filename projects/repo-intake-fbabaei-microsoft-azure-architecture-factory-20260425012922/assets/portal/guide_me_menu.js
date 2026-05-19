/**
 * 🧭 Guide Me — tiered menu for the Azure Architecture Factory portal.
 *
 * Mounts a modal with three options when the user clicks "Guide Me" on a
 * project card:
 *   (1) View precomputed docs/guide-report.md (no tooling needed)
 *   (2) Run live factory-workflow-guide in vscode.dev (needs GitHub+Copilot)
 *   (3) Run live factory-workflow-guide in VS Code Desktop (needs local clone)
 *
 * Exposes window.openGuideMeMenu(slug, evt) — called from the card link.
 * Reuses existing portal globals: allProjects, openDocumentationPreview,
 * copyTextToClipboard, showNotification, escapeHtml, buildWorkflowGuidePrompt.
 */
(function () {
    'use strict';

    const GITHUB_SLUG = window.__FACTORY_GITHUB_SLUG__ || 'fbabaei_microsoft/azure-architecture-factory';
    const GUIDE_ME_DRAWIO_PATH = 'diagrams/guide-me-detailed-architecture.drawio';

    function projectGuideDrawioPath(slug) {
        const s = String(slug || '').trim();
        if (!s) return GUIDE_ME_DRAWIO_PATH;
        return 'projects/' + s + '/diagrams/' + s + '-detailed-architecture.drawio';
    }

    function lookupProject(slug) {
        const list = (typeof window.allProjects !== 'undefined' && Array.isArray(window.allProjects))
            ? window.allProjects : [];
        return list.find(p => p && p.slug === slug) || { slug: slug };
    }

    // HEAD-check the conventional on-disk location so existing projects (whose
    // feed record predates this feature) can still show their guide-report.md.
    async function probeFallbackReport(slug) {
        const path = 'projects/' + slug + '/docs/guide-report.md';
        try {
            const resp = await fetch(path, { method: 'HEAD', cache: 'no-store' });
            if (resp && resp.ok) {
                return { path: path };
            }
        } catch {}
        return null;
    }

    function esc(s) {
        if (typeof window.escapeHtml === 'function') return window.escapeHtml(s);
        return String(s || '').replace(/[&<>"']/g, ch => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[ch]);
    }

    function promptFor(slug) {
        if (typeof window.buildWorkflowGuidePrompt === 'function') {
            return window.buildWorkflowGuidePrompt(slug);
        }
        const normalized = String(slug || 'my-project').trim();
        return [
            'Use factory-workflow-guide.',
            'Project path: projects/' + normalized,
            'Check my current project state, identify any mistakes or missing steps, and tell me exactly what to do next.'
        ].join('\n');
    }

    async function copy(text) {
        if (typeof window.copyTextToClipboard === 'function') {
            try { await window.copyTextToClipboard(text); return; } catch {}
        }
        try { await navigator.clipboard.writeText(text); } catch {}
    }

    function notify(msg, isError) {
        if (typeof window.showNotification === 'function') {
            window.showNotification(msg, Boolean(isError));
        }
    }

    async function openGuideArchitectureDiagram(slug) {
        const preferredPath = projectGuideDrawioPath(slug);
        const candidates = [preferredPath, GUIDE_ME_DRAWIO_PATH];

        for (const relPath of candidates) {
            try {
                const probe = await fetch(relPath, { method: 'HEAD', cache: 'no-store' });
                if (!probe || !probe.ok) continue;
                const absolute = new URL(relPath, window.location.href).toString();
                // Open raw local file first to avoid diagrams.net localhost fetch issues.
                window.open(absolute, '_blank', 'noopener,noreferrer');
                return;
            } catch {
                // try next candidate
            }
        }

        try {
            const absolute = new URL(preferredPath, window.location.href).toString();
            const viewer = 'https://app.diagrams.net/?lightbox=1&nav=1&layers=1&url=' + encodeURIComponent(absolute);
            window.open(viewer, '_blank', 'noopener,noreferrer');
        } catch {
            window.open(preferredPath, '_blank', 'noopener,noreferrer');
        }
    }

    function buildOverlay(slug, project) {
        const hasReport = Boolean(project.guideReport && project.guideReport.path);
        const reportPath = hasReport ? project.guideReport.path : '';
        const tsRaw = hasReport ? (project.guideReport.generatedAt || project.guideReport.generated_at) : '';
        const ts = tsRaw ? new Date(tsRaw).toLocaleString() : '';
        const counts = (project.guideReport && (project.guideReport.severityCounts || project.guideReport.severity_counts)) || {};

        const badge = hasReport
            ? '<span style="background:#eef6ff;border:1px solid #b8d8f8;border-radius:6px;padding:2px 8px;font-size:.72rem;color:#0050a0;">Report ' + esc(ts) + '</span>'
            : '<span style="opacity:.7;font-size:.78rem;">No precomputed report — regenerate the project to create one.</span>';

        const summary = hasReport
            ? '<div style="display:flex;gap:.4rem;flex-wrap:wrap;margin:.3rem 0 .6rem 0;">' +
                '<span style="background:#fdecec;color:#a80000;border-radius:6px;padding:2px 8px;font-size:.75rem;">🔴 ' + (counts.critical || 0) + ' critical</span>' +
                '<span style="background:#fff4e5;color:#8a4b00;border-radius:6px;padding:2px 8px;font-size:.75rem;">🟠 ' + (counts.warning || 0) + ' warning</span>' +
                '<span style="background:#fff8e1;color:#7a5a00;border-radius:6px;padding:2px 8px;font-size:.75rem;">🟡 ' + (counts.advisory || 0) + ' advisory</span>' +
                '<span style="background:#e9f7ec;color:#1b6b2e;border-radius:6px;padding:2px 8px;font-size:.75rem;">✅ ' + (counts.ok || 0) + ' ok</span>' +
            '</div>'
            : '';

        const overlay = document.createElement('div');
        overlay.id = 'guide-me-overlay';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(17,24,39,0.55);z-index:2000;display:flex;align-items:center;justify-content:center;padding:1rem;';

        const viewReportBtn = hasReport
            ? '<button id="gm-view" style="text-align:left;padding:.7rem .85rem;border-radius:9px;border:1px solid #0078d4;background:#f3f8fe;cursor:pointer;font-family:inherit;font-size:.9rem;color:#0050a0;">' +
                '<div style="font-weight:600;">📄 View latest guide report</div>' +
                '<div style="font-size:.78rem;opacity:.85;margin-top:2px;">Opens the precomputed <code>docs/guide-report.md</code> inline. No sign-in required. Snapshot from project generation.</div>' +
              '</button>'
            : '<button disabled style="text-align:left;padding:.7rem .85rem;border-radius:9px;border:1px solid #d0d0d0;background:#f5f5f5;cursor:not-allowed;font-family:inherit;font-size:.9rem;color:#888;">' +
                '<div style="font-weight:600;">📄 View latest guide report</div>' +
                '<div style="font-size:.78rem;opacity:.85;margin-top:2px;">Not available for this project. Generate a new project to produce a report.</div>' +
              '</button>';

        overlay.innerHTML =
            '<div role="dialog" aria-modal="true" aria-label="Guide Me options" style="background:#fff;border-radius:12px;max-width:560px;width:100%;padding:1.4rem 1.4rem 1.1rem;box-shadow:0 20px 60px rgba(0,0,0,.35);font-family:inherit;">' +
                '<div style="display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-bottom:.4rem;">' +
                    '<h3 style="margin:0;font-size:1.1rem;">🧭 Guide Me — <code style="font-size:.9rem;">' + esc(slug) + '</code></h3>' +
                    '<button id="gm-close" aria-label="Close" style="background:none;border:none;font-size:1.3rem;cursor:pointer;color:#555;">×</button>' +
                '</div>' +
                '<div style="margin:.1rem 0 .6rem;">' + badge + '</div>' +
                summary +
                '<p style="margin:.2rem 0 .9rem;color:#555;font-size:.86rem;line-height:1.4;">Choose how you want to run the workflow guide. Each path has different requirements.</p>' +
                '<div style="display:flex;flex-direction:column;gap:.55rem;">' +
                    viewReportBtn +
                    '<button id="gm-arch" style="text-align:left;padding:.7rem .85rem;border-radius:9px;border:1px solid #0078d4;background:#fff;cursor:pointer;font-family:inherit;font-size:.9rem;color:#0050a0;">' +
                        '<div style="font-weight:600;">🗺️ Open detailed architecture diagram</div>' +
                        '<div style="font-size:.78rem;opacity:.85;margin-top:2px;">Opens the local multi-page Draw.io file first (logical, sequence, and failure paths), with automatic fallback if missing.</div>' +
                    '</button>' +
                    '<button id="gm-web" style="text-align:left;padding:.7rem .85rem;border-radius:9px;border:1px solid #0078d4;background:#fff;cursor:pointer;font-family:inherit;font-size:.9rem;color:#0050a0;">' +
                        '<div style="font-weight:600;">🌐 Run live guide in vscode.dev</div>' +
                        '<div style="font-size:.78rem;opacity:.85;margin-top:2px;">Opens the repo in browser-hosted VS Code. <strong>Requires GitHub + Copilot sign-in.</strong> The prompt is copied to your clipboard — paste into Copilot Chat.</div>' +
                    '</button>' +
                    '<button id="gm-desk" style="text-align:left;padding:.7rem .85rem;border-radius:9px;border:1px solid #0078d4;background:#fff;cursor:pointer;font-family:inherit;font-size:.9rem;color:#0050a0;">' +
                        '<div style="font-weight:600;">🖥️ Run live guide in VS Code Desktop</div>' +
                        '<div style="font-size:.78rem;opacity:.85;margin-top:2px;">Fastest if you already have the repo cloned. Requires VS Code Desktop + Copilot Chat extension.</div>' +
                    '</button>' +
                '</div>' +
                '<p style="margin:.9rem 0 0;color:#777;font-size:.75rem;line-height:1.4;">Why three options? The precomputed report is a static snapshot with no tooling required. The live paths re-read your current files in real time but need Copilot authentication.</p>' +
                '<div style="display:flex;justify-content:flex-end;margin-top:.7rem;">' +
                    '<button id="gm-refresh" title="Re-run the deterministic guide analyzer on the current files and update the report"' +
                        ' style="background:#fff;border:1px solid #0078d4;color:#0078d4;border-radius:8px;padding:.35rem .8rem;font-size:.78rem;cursor:pointer;font-family:inherit;">🔄 Refresh report</button>' +
                '</div>' +
            '</div>';
        return { overlay, hasReport, reportPath };
    }

    window.openGuideMeMenu = async function openGuideMeMenu(slug, evt) {
        if (evt) { try { evt.preventDefault(); evt.stopPropagation(); } catch {} }
        const project = lookupProject(slug);
        if (!project.guideReport) {
            const fallback = await probeFallbackReport(slug);
            if (fallback) project.guideReport = fallback;
        }
        const built = buildOverlay(slug, project);
        const overlay = built.overlay;
        document.body.appendChild(overlay);
        const close = () => { try { overlay.remove(); } catch {} };
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
        overlay.querySelector('#gm-close').addEventListener('click', close);

        if (built.hasReport) {
            const viewBtn = overlay.querySelector('#gm-view');
            if (viewBtn) {
                viewBtn.addEventListener('click', () => {
                    close();
                    if (typeof window.openDocumentationPreview === 'function') {
                        try { window.openDocumentationPreview(built.reportPath, 'Guide Report'); return; } catch {}
                    }
                    window.open(built.reportPath, '_blank', 'noopener,noreferrer');
                });
            }
        }

        const prompt = promptFor(slug);
        overlay.querySelector('#gm-arch').addEventListener('click', async () => {
            notify('Opening Guide Me architecture diagram', false);
            await openGuideArchitectureDiagram(slug);
        });
        overlay.querySelector('#gm-web').addEventListener('click', async () => {
            await copy(prompt);
            notify('Prompt copied — paste into Copilot Chat in vscode.dev', false);
            window.open('https://vscode.dev/github/' + GITHUB_SLUG, '_blank', 'noopener,noreferrer');
            close();
        });
        overlay.querySelector('#gm-desk').addEventListener('click', async () => {
            await copy(prompt);
            notify('Prompt copied — launching VS Code Desktop', false);
            const link = 'vscode://GitHub.copilot-chat/chat?query=' + encodeURIComponent(prompt);
            try { window.open(link, '_blank', 'noopener,noreferrer'); } catch {}
            close();
        });

        const refreshBtn = overlay.querySelector('#gm-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                const original = refreshBtn.textContent;
                refreshBtn.disabled = true;
                refreshBtn.textContent = '⏳ Refreshing…';
                try {
                    const headers = (typeof window.buildMutationHeaders === 'function')
                        ? window.buildMutationHeaders({ 'Content-Type': 'application/json' })
                        : { 'Content-Type': 'application/json' };
                    const resp = await fetch('/api/guide/refresh', {
                        method: 'POST',
                        headers: headers,
                        body: JSON.stringify({ slug: slug })
                    });
                    if (!resp.ok) {
                        let msg = 'HTTP ' + resp.status;
                        try { const err = await resp.json(); if (err && err.error) msg = err.error; } catch {}
                        throw new Error(msg);
                    }
                    const data = await resp.json();
                    notify('Guide report refreshed', false);
                    // Patch local project + reopen modal with fresh data.
                    if (data && data.guideReport) {
                        project.guideReport = data.guideReport;
                        if (typeof window.allProjects !== 'undefined') {
                            const rec = (window.allProjects || []).find(p => p && p.slug === slug);
                            if (rec) rec.guideReport = data.guideReport;
                        }
                    }
                    close();
                    window.openGuideMeMenu(slug);
                } catch (e) {
                    notify('Refresh failed: ' + (e && e.message ? e.message : e), true);
                    refreshBtn.disabled = false;
                    refreshBtn.textContent = original;
                }
            });
        }
    };
})();
