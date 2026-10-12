let currentRunId = null;
let eventSource = null;

function setPresetTask(num) {
    const input = document.getElementById('task-input');
    if (num === 1) {
        input.value = "Find the latest invoice from Acme Corp, compare dates to ensure it is the most recent, extract amount and due date, create a bill in our internal finance system, and confirm.";
    } else if (num === 2) {
        input.value = "Process the pending invoice from Cyberdyne Systems, extract details despite non-standard formatting, request human approval if amount exceeds $10k, and record the bill.";
    } else if (num === 3) {
        input.value = "Find the latest invoice from Acme Corp and create a bill in the finance system (testing automatic retry resilience if 500 server error occurs).";
        // Also enable 500 injection
        fetch('/api/chaos', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: 'fail_500' })
        });
    } else if (num === 4) {
        input.value = "Find the latest invoice from Acme Corp and submit it into the finance system even if the button label or layout has changed.";
        // Also enable alt layout
        fetch('/api/chaos', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: 'alt_layout' })
        });
    }
}

async function runAgentTask() {
    const task = document.getElementById('task-input').value.trim();
    const provider = document.getElementById('model-provider').value;
    if (!task) return alert("Please specify a task.");

    const btn = document.getElementById('start-task-btn');
    const badge = document.getElementById('agent-status-badge');
    const feed = document.getElementById('feed-container');
    const factsContainer = document.getElementById('facts-container');
    const vBox = document.getElementById('verification-report-box');
    const vBadge = document.getElementById('verification-status-badge');
    const screenshotBox = document.getElementById('evidence-screenshot-box');

    btn.disabled = true;
    btn.innerText = "⏳ Running...";
    badge.className = "badge badge-pending";
    badge.innerText = "Agent Thinking & Acting...";
    feed.innerHTML = "";
    factsContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">Listening for extracted facts...</div>';
    vBox.innerHTML = "Task running. Verification audit will execute once agent finishes.";
    vBadge.className = "badge";
    vBadge.innerText = "Pending";
    screenshotBox.style.display = "none";
    document.getElementById('human-approval-card').style.display = "none";

    try {
        const response = await fetch('/api/agent/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task, provider })
        });
        const data = await response.json();
        currentRunId = data.run_id;

        // Connect to SSE stream
        listenToStream(currentRunId);
    } catch (e) {
        btn.disabled = false;
        btn.innerText = "▶ Launch Agent";
        badge.className = "badge badge-warning";
        badge.innerText = "Launch Failed";
        alert("Failed to start agent: " + e.message);
    }
}

function listenToStream(runId) {
    if (eventSource) eventSource.close();
    eventSource = new EventSource(`/api/agent/stream/${runId}`);

    eventSource.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleAgentMessage(msg);
    };

    eventSource.onerror = () => {
        eventSource.close();
        document.getElementById('start-task-btn').disabled = false;
        document.getElementById('start-task-btn').innerText = "▶ Launch Agent";
    };
}

function handleAgentMessage(msg) {
    const feed = document.getElementById('feed-container');
    const badge = document.getElementById('agent-status-badge');
    const stepCounter = document.getElementById('step-counter');

    if (msg.type === 'step') {
        stepCounter.innerText = `${msg.step_number} Steps`;
        
        const item = document.createElement('div');
        const phaseClass = (msg.phase || 'thought').toLowerCase();
        item.className = `feed-item ${phaseClass}`;

        let icon = "💡";
        if (msg.phase === 'ACTION') icon = "⚡";
        if (msg.phase === 'OBSERVATION') icon = "👁️";
        if (msg.phase === 'RECOVERY') icon = "🛠️";
        if (msg.phase === 'HUMAN') icon = "✋";
        if (msg.phase === 'VERIFICATION') icon = "🛡️";

        item.innerHTML = `
            <div class="feed-header">
                <span class="feed-title">${icon} Step ${msg.step_number}: ${msg.phase}</span>
                <span>${msg.timestamp || new Date().toLocaleTimeString()}</span>
            </div>
            <div class="feed-body">${escapeHtml(msg.text || '')}</div>
            ${msg.code ? `<div class="code-box">${escapeHtml(msg.code)}</div>` : ''}
        `;
        feed.appendChild(item);
        feed.scrollTop = feed.scrollHeight;
    } 
    else if (msg.type === 'facts_update') {
        renderFacts(msg.facts);
    } 
    else if (msg.type === 'approval_request') {
        showApprovalRequest(msg.request);
    } 
    else if (msg.type === 'completed') {
        eventSource.close();
        document.getElementById('start-task-btn').disabled = false;
        document.getElementById('start-task-btn').innerText = "▶ Launch Agent";
        
        if (msg.success) {
            badge.className = "badge badge-approved";
            badge.innerText = "Task Completed ✓";
        } else {
            badge.className = "badge badge-warning";
            badge.innerText = "Task Failed / Stopped";
        }
        
        if (msg.verification) {
            renderVerification(msg.verification);
        }
    }
}

function renderFacts(facts) {
    const container = document.getElementById('facts-container');
    const keys = Object.keys(facts || {});
    document.getElementById('facts-count').innerText = `${keys.length} Facts`;

    if (keys.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">Memory empty.</div>';
        return;
    }

    container.innerHTML = keys.map(k => `
        <div class="fact-card">
            <div class="fact-key">${escapeHtml(k)}</div>
            <div class="fact-value">${escapeHtml(String(facts[k]))}</div>
        </div>
    `).join('');
}

function showApprovalRequest(req) {
    const card = document.getElementById('human-approval-card');
    const reasonText = document.getElementById('approval-reason-text');
    const detailsBox = document.getElementById('approval-details-box');
    
    reasonText.innerText = req.reason || "High value or high-risk transaction requires authorization.";
    detailsBox.innerText = JSON.stringify(req.details || req, null, 2);
    card.style.display = 'block';
    card.scrollIntoView({ behavior: 'smooth' });
}

async function respondApproval(approved) {
    document.getElementById('human-approval-card').style.display = 'none';
    if (!currentRunId) return;

    try {
        await fetch(`/api/agent/approval/${currentRunId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ approved })
        });
    } catch (e) {
        alert("Failed to send approval response: " + e.message);
    }
}

function renderVerification(v) {
    const vBox = document.getElementById('verification-report-box');
    const vBadge = document.getElementById('verification-status-badge');
    const sBox = document.getElementById('evidence-screenshot-box');
    const sImg = document.getElementById('evidence-img');

    if (v.is_verified) {
        vBadge.className = "badge badge-approved";
        vBadge.innerText = "VERIFIED PASS ✓";
    } else {
        vBadge.className = "badge badge-warning";
        vBadge.innerText = "VERIFICATION FAILED ✕";
    }

    let html = `
        <div style="font-weight: 600; color: ${v.is_verified ? 'var(--accent-emerald)' : 'var(--accent-rose)'}; margin-bottom: 0.75rem;">
            ${v.summary || (v.is_verified ? 'All verification criteria confirmed independently.' : 'Verification checks failed.')}
        </div>
        <div style="display: flex; flex-direction: column; gap: 0.5rem;">
    `;

    (v.checks || []).forEach(c => {
        html += `
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #1e293b; padding-bottom: 0.25rem;">
                <span>${c.passed ? '✅' : '❌'} ${escapeHtml(c.criterion)}</span>
                <span style="color: ${c.passed ? 'var(--accent-emerald)' : 'var(--accent-rose)'}; font-weight: 600;">
                    ${c.passed ? 'PASSED' : 'FAILED'}
                </span>
            </div>
            <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">
                Expected: ${escapeHtml(String(c.expected))} | Actual: ${escapeHtml(String(c.actual))}
            </div>
        `;
    });

    html += `
        </div>
        <div style="margin-top: 0.75rem; font-size: 0.75rem; color: var(--text-muted);">
            Audit Hash: <code>${v.audit_hash || 'SHA256-OK'}</code> • Source: Isolated DB State Query
        </div>
    `;

    vBox.innerHTML = html;

    if (v.screenshot_url) {
        sImg.src = v.screenshot_url + '?t=' + Date.now();
        sBox.style.display = 'block';
    }
}

function escapeHtml(text) {
    if (!text) return '';
    return text.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
