/**
 * Pokant API Client
 *
 * Reusable fetch wrapper for all dashboard pages.
 *
 * Usage:
 *   const data = await api.getDashboard();
 *   const patterns = await api.getPatterns();
 */

class PokantAPI {
    constructor(baseURL = 'http://localhost:8000') {
        this.baseURL = baseURL;
        this.customerId = this._getCustomerId();
    }

    /** Resolve customer ID from localStorage or URL params. */
    _getCustomerId() {
        let id = localStorage.getItem('pokant_customer_id');
        if (!id) {
            const params = new URLSearchParams(window.location.search);
            id = params.get('customer_id');
            if (id) localStorage.setItem('pokant_customer_id', id);
        }
        return id;
    }

    /** Generic fetch with JSON handling and error propagation. */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        };

        const response = await fetch(url, config);

        if (!response.ok) {
            let detail = `HTTP ${response.status}`;
            try {
                const body = await response.json();
                detail = body.detail || detail;
            } catch (_) { /* ignore */ }
            throw new Error(detail);
        }

        return response.json();
    }

    // ── Dashboard ──────────────────────────────────────────────────

    getDashboard(customerId) {
        const cid = customerId || this.customerId;
        if (!cid) throw new Error('No customer ID');
        return this.request(`/api/dashboard/${cid}`);
    }

    getPatterns(customerId) {
        const cid = customerId || this.customerId;
        if (!cid) throw new Error('No customer ID');
        return this.request(`/api/patterns/${cid}`);
    }

    // ── Variants ───────────────────────────────────────────────────

    getVariants(patternId) {
        return this.request(`/api/variants/${patternId}`);
    }

    regenerateVariants(patternId) {
        return this.request(`/api/variants/${patternId}/regenerate`, { method: 'POST' });
    }

    // ── A/B Tests ──────────────────────────────────────────────────

    deployTest(data) {
        return this.request('/api/tests/deploy', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    getTestResults(testId) {
        return this.request(`/api/tests/${testId}`);
    }

    promoteVariant(testId) {
        return this.request(`/api/tests/${testId}/promote`, { method: 'POST' });
    }

    cancelTest(testId) {
        return this.request(`/api/tests/${testId}/cancel`, { method: 'POST' });
    }

    listTests(customerId) {
        const cid = customerId || this.customerId;
        return this.request(`/api/tests?customer_id=${cid}`);
    }

    // ── Onboarding ─────────────────────────────────────────────────

    async onboard(data) {
        const res = await this.request('/api/onboard', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        if (res.id) {
            this.customerId = res.id;
            localStorage.setItem('pokant_customer_id', res.id);
        }
        return res;
    }

    // ── Health ──────────────────────────────────────────────────────

    healthCheck() {
        return this.request('/health');
    }
}

// ── UI Helpers (shared across pages) ──────────────────────────────

function showLoadingOverlay(message) {
    let overlay = document.getElementById('pokant-loading');
    if (overlay) { overlay.remove(); }
    overlay = document.createElement('div');
    overlay.id = 'pokant-loading';
    overlay.innerHTML = `
        <div style="position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999">
            <div style="text-align:center;color:#fff">
                <div style="width:40px;height:40px;border:3px solid rgba(255,255,255,0.3);border-top-color:#3b82f6;border-radius:50%;animation:pokant-spin 0.8s linear infinite;margin:0 auto 12px"></div>
                <p style="font-size:14px">${message || 'Loading...'}</p>
            </div>
        </div>
        <style>@keyframes pokant-spin{to{transform:rotate(360deg)}}</style>
    `;
    document.body.appendChild(overlay);
}

function hideLoadingOverlay() {
    const el = document.getElementById('pokant-loading');
    if (el) el.remove();
}

function showErrorBanner(message) {
    hideLoadingOverlay();
    let banner = document.getElementById('pokant-error');
    if (banner) banner.remove();
    banner = document.createElement('div');
    banner.id = 'pokant-error';
    banner.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#ef4444;color:#fff;padding:12px 20px;z-index:9998;display:flex;align-items:center;justify-content:space-between;font-size:14px;animation:pokant-slide-down 0.3s ease';
    banner.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()" style="background:none;border:none;color:#fff;font-size:20px;cursor:pointer;padding:0 4px">&times;</button>
        <style>@keyframes pokant-slide-down{from{transform:translateY(-100%)}to{transform:translateY(0)}}</style>
    `;
    document.body.prepend(banner);
}

function showSuccessBanner(message) {
    let banner = document.getElementById('pokant-success');
    if (banner) banner.remove();
    banner = document.createElement('div');
    banner.id = 'pokant-success';
    banner.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#10b981;color:#fff;padding:12px 20px;z-index:9998;display:flex;align-items:center;gap:8px;font-size:14px;animation:pokant-slide-down 0.3s ease';
    banner.innerHTML = `<span>&#10003;</span><span>${message}</span>`;
    document.body.prepend(banner);
    setTimeout(() => banner.remove(), 5000);
}

// Global instance
const api = new PokantAPI();
