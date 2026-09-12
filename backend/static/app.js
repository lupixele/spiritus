/**
 * Spiritus Disaster Decision & Operational Response Workbench Frontend Controller.
 * 
 * Manages:
 * - Real-time USGS earthquake and NASA EONET wildfire observation feed display
 * - 3D Visual Observatory Globe & 2D Tactical Graph switcher
 * - Light and Dark theme persistence and live Three.js scene updates
 * - Interactive judge road damage and shock injection controls
 * - 10 Mandatory crisis capabilities execution and evidence verification
 * - Real-time SSE streaming agent thoughts, tool observations, and critic reviews
 * - Incident revision tracking and race protection alerts
 */
import { DisasterGlobe } from './globe.js';

let globeInstance = null;
let currentExerciseState = null;
let liveFeedsData = null;
let activeFilter = 'all';
let authoritativeRevision = 1;

const NODE_SVG_COORDS = {
  "N1": { x: 260, y: 190, name: "Port Area" },
  "N2": { x: 330, y: 150, name: "Beach Rd" },
  "N3": { x: 280, y: 130, name: "Jagadamba" },
  "N4": { x: 120, y: 220, name: "Gajuwaka" },
  "N5": { x: 360, y: 40,  name: "Madhurawada" },
  "N6": { x: 80,  y: 90,  name: "Pendurthi" },
  "N7": { x: 350, y: 180, name: "RK Beach" },
  "N8": { x: 200, y: 80,  name: "Simhachalam" },
};

document.addEventListener('DOMContentLoaded', async () => {
  initGlobe();
  bindUIEvents();
  await refreshAllData();

  setInterval(refreshAllData, 30000);
});

function initGlobe() {
  const mountEl = document.getElementById('globe-container');
  if (!mountEl) return;

  globeInstance = new DisasterGlobe(mountEl, {
    dprCap: 1.0,
    targetFps: 30,
    onSelect: handleItemSelection,
  });
  globeInstance.init();
}

function bindUIEvents() {
  // Tab Switching between Agent Chat and Tactical Data
  const tabChat = document.getElementById('tab-btn-chat');
  const tabTactical = document.getElementById('tab-btn-tactical');
  const paneChat = document.getElementById('pane-chat-view');
  const paneTactical = document.getElementById('pane-tactical-view');

  if (tabChat && tabTactical && paneChat && paneTactical) {
    tabChat.addEventListener('click', () => {
      tabChat.classList.add('active');
      tabTactical.classList.remove('active');
      paneChat.style.display = 'flex';
      paneTactical.style.display = 'none';
    });

    tabTactical.addEventListener('click', () => {
      tabTactical.classList.add('active');
      tabChat.classList.remove('active');
      paneTactical.style.display = 'flex';
      paneChat.style.display = 'none';
    });
  }

  // Capability chips in Chat workspace
  document.querySelectorAll('.quick-caps-scroll .cap-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const capNum = btn.dataset.cap;
      runCapabilityPrompt(capNum);
    });
  });

  // Mode toggles
  const btnGlobe = document.getElementById('btn-mode-globe');
  const btnExercise = document.getElementById('btn-mode-exercise');
  const globeWrapper = document.getElementById('globe-stage-wrapper');
  const tacticalWrapper = document.getElementById('tactical-map-wrapper');

  btnGlobe.addEventListener('click', () => {
    btnGlobe.classList.add('active');
    btnExercise.classList.remove('active');
    globeWrapper.style.display = 'block';
    tacticalWrapper.style.display = 'none';
  });

  btnExercise.addEventListener('click', () => {
    btnExercise.classList.add('active');
    btnGlobe.classList.remove('active');
    globeWrapper.style.display = 'none';
    tacticalWrapper.style.display = 'flex';
    renderTacticalNetwork();
  });

  // Theme Toggle (Dark / Light)
  const btnTheme = document.getElementById('btn-toggle-theme');
  if (btnTheme) {
    btnTheme.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('spiritus_theme', next);
      if (globeInstance) {
        globeInstance.setTheme(next);
      }
      if (tacticalWrapper.style.display !== 'none') {
        renderTacticalNetwork();
      }
    });
  }

  // Filter chips
  document.querySelectorAll('.filter-strip .chip').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-strip .chip').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilter = btn.dataset.filter;
      renderIncidentFeedList();
    });
  });

  // Refresh
  document.getElementById('btn-refresh-data').addEventListener('click', refreshAllData);

  // Telemetry Modal Controls
  const telemModal = document.getElementById('telemetry-modal');
  const btnOpenTelem = document.getElementById('btn-open-telemetry');
  const btnCloseTelem = document.getElementById('btn-close-telemetry');

  async function updateTelemetryUI() {
    try {
      const [cfgRes, exRes] = await Promise.all([
        fetch('/api/config'),
        fetch('/api/exercise/state')
      ]);
      if (cfgRes.ok) {
        const cfg = await cfgRes.json();
        const mEl = document.getElementById('telem-model');
        const pEl = document.getElementById('telem-provider');
        if (mEl) mEl.textContent = cfg.active_model || 'antigravity/gemini-3.8-flash-tiered';
        if (pEl) pEl.textContent = cfg.provider_url || 'https://omniroute.lupixele.online/v1';
      }
      if (exRes.ok) {
        const ex = await exRes.json();
        const rEl = document.getElementById('telem-revision');
        const cEl = document.getElementById('telem-cuts');
        const sEl = document.getElementById('telem-shelter-pct');
        const misEl = document.getElementById('telem-missions');

        if (rEl) rEl.textContent = `#${ex.revision || 1}`;
        if (cEl) cEl.textContent = `${(ex.disrupted_roads || []).length} blocked`;
        if (misEl) misEl.textContent = `${(ex.aid_requests || []).length} active`;

        if (sEl && ex.shelters) {
          const total = ex.shelters.reduce((acc, s) => acc + (s.max_capacity || 0), 0);
          const occ = ex.shelters.reduce((acc, s) => acc + (s.current_occupancy || 0), 0);
          const pct = total > 0 ? Math.round((occ / total) * 100) : 0;
          sEl.textContent = `${pct}% (${occ}/${total} beds)`;
        }
      }
    } catch (e) {
      console.warn('Failed to update telemetry', e);
    }
  }

  if (btnOpenTelem && telemModal) {
    btnOpenTelem.addEventListener('click', () => {
      updateTelemetryUI();
      telemModal.style.display = 'flex';
    });
  }

  if (btnCloseTelem && telemModal) {
    btnCloseTelem.addEventListener('click', () => {
      telemModal.style.display = 'none';
    });
  }

  // Settings Modal Controls
  const modal = document.getElementById('settings-modal');
  const btnOpenSettings = document.getElementById('btn-open-settings');
  const btnCloseSettings = document.getElementById('btn-close-settings');
  const btnCancelSettings = document.getElementById('btn-cancel-settings');
  const btnSaveSettings = document.getElementById('btn-save-settings');
  const inputUrl = document.getElementById('cfg-provider-url');
  const inputModel = document.getElementById('cfg-active-model');
  const inputKey = document.getElementById('cfg-api-key');
  const cfgMsg = document.getElementById('cfg-status-msg');

  async function loadConfigIntoModal() {
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const d = await res.json();
        inputUrl.value = d.provider_url || '';
        inputModel.value = d.active_model || '';
        inputKey.value = '';
        inputKey.placeholder = d.has_api_key ? d.api_key_masked : 'Optional if routed through OmniRoute';
      }
    } catch (e) {
      console.warn('Failed to load config', e);
    }
  }

  if (btnOpenSettings && modal) {
    btnOpenSettings.addEventListener('click', () => {
      loadConfigIntoModal();
      modal.style.display = 'flex';
      cfgMsg.style.display = 'none';
    });
  }

  const hideModal = () => { if (modal) modal.style.display = 'none'; };
  if (btnCloseSettings) btnCloseSettings.addEventListener('click', hideModal);
  if (btnCancelSettings) btnCancelSettings.addEventListener('click', hideModal);

  if (btnSaveSettings) {
    btnSaveSettings.addEventListener('click', async () => {
      const payload = {
        provider_url: inputUrl.value.trim(),
        active_model: inputModel.value.trim(),
      };
      if (inputKey.value.trim()) {
        payload.api_key = inputKey.value.trim();
      }
      try {
        const res = await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          cfgMsg.style.display = 'block';
          setTimeout(() => { hideModal(); }, 900);
        } else {
          alert('Failed to save configuration.');
        }
      } catch (e) {
        alert('Network error saving configuration.');
      }
    });
  }

  // Judge Controls
  document.getElementById('btn-apply-road-damage').addEventListener('click', applyJudgeRoadDamage);
  document.getElementById('btn-shock-overflow').addEventListener('click', () => applyJudgeShock('shelter_overflow'));
  document.getElementById('btn-reset-exercise').addEventListener('click', resetExerciseState);

  // Agent prompt submit
  document.getElementById('btn-execute-agent').addEventListener('click', submitAgentInstruction);
  document.getElementById('agent-user-prompt').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submitAgentInstruction();
  });

  // 10 Capabilities quick buttons
  document.querySelectorAll('.cap-pill').forEach(badge => {
    badge.addEventListener('click', () => {
      const capNum = badge.dataset.cap;
      triggerCapabilityDemo(capNum);
    });
  });

  // Quick 10-cap audit button in topbar
  document.getElementById('btn-quick-audit').addEventListener('click', () => {
    submitAgentInstructionWithText("Run comprehensive 10 capabilities operational audit for Visakhapatnam earthquake response. Check all road closures, calculate safe evac corridors from Port N1, inspect shelter capacities, and verify rescue deployment priorities.");
  });
}

async function refreshAllData() {
  try {
    // 1. Fetch live feeds
    const feedResp = await fetch('/api/feeds/disasters');
    if (feedResp.ok) {
      liveFeedsData = await feedResp.json();
      updateGlobeFeeds(liveFeedsData);
      updateWeatherBanner(liveFeedsData.weather);
    }

    // 2. Fetch exercise state
    const exResp = await fetch('/api/exercise/state');
    if (exResp.ok) {
      currentExerciseState = await exResp.json();
      authoritativeRevision = currentExerciseState.revision || 1;
      updateRevisionDisplay(authoritativeRevision);
      renderShelterTable(currentExerciseState.shelters);
      if (document.getElementById('tactical-map-wrapper').style.display !== 'none') {
        renderTacticalNetwork();
      }
    }

    renderIncidentFeedList();
  } catch (err) {
    console.error("Failed to refresh data:", err);
  }
}

function updateRevisionDisplay(rev) {
  const revEl = document.getElementById('incident-rev-tag');
  if (revEl) revEl.textContent = `REVISION: #${rev}`;
}

function updateWeatherBanner(weather) {
  const el = document.getElementById('vizag-weather-val');
  if (!el || !weather) return;
  el.textContent = `${weather.temperature || 28}°C, Wind ${weather.windspeed || 12} km/h (${weather.type})`;
}

function updateGlobeFeeds(data) {
  if (!globeInstance) return;
  const quakes = (data.earthquakes && data.earthquakes.events) || [];
  const fires = (data.wildfires && data.wildfires.events) || [];

  document.getElementById('count-quakes').textContent = `${quakes.length} (${data.earthquakes?.status || 'live'})`;
  document.getElementById('count-wildfires').textContent = `${fires.length} (${data.wildfires?.status || 'live'})`;

  globeInstance.setEvents(quakes, fires);
}

function renderIncidentFeedList() {
  const listEl = document.getElementById('incident-feed-list');
  if (!listEl) return;
  listEl.innerHTML = '';

  // Exercise Card (Synthetic Operation)
  if (activeFilter === 'all' || activeFilter === 'exercise') {
    const exCard = document.createElement('div');
    exCard.className = 'incident-card exercise-highlight';
    exCard.innerHTML = `
      <div class="card-top">
        <span class="tag-badge tag-exercise">SYNTHETIC_EXERCISE</span>
        <span class="time-label">M6.8 SIMULATION</span>
      </div>
      <div class="card-title-text">Visakhapatnam Coastal Response</div>
      <div class="card-desc-text">Seismic impact zone. ${currentExerciseState?.summary?.disrupted_road_segments || 1} road closures active. Casualties: ${currentExerciseState?.summary?.reported_casualties || 0}.</div>
    `;
    exCard.addEventListener('click', () => {
      document.getElementById('btn-mode-exercise').click();
    });
    listEl.appendChild(exCard);
  }

  // Quakes
  if (liveFeedsData?.earthquakes?.events && (activeFilter === 'all' || activeFilter === 'earthquakes')) {
    const quakes = liveFeedsData.earthquakes.events.slice(0, 15);
    for (const q of quakes) {
      const card = document.createElement('div');
      card.className = 'incident-card quake-highlight';
      card.innerHTML = `
        <div class="card-top">
          <span class="tag-badge tag-quake">M${Number(q.mag).toFixed(1)}</span>
          <span class="time-label">USGS LIVE</span>
        </div>
        <div class="card-title-text">${q.place}</div>
        <div class="card-desc-text">Depth: ${q.depth}km | Lat: ${Number(q.lat).toFixed(2)}, Lon: ${Number(q.lon).toFixed(2)}</div>
      `;
      card.addEventListener('click', () => {
        if (globeInstance) globeInstance.focusLocation(q.lat, q.lon);
      });
      listEl.appendChild(card);
    }
  }

  // Wildfires
  if (liveFeedsData?.wildfires?.events && (activeFilter === 'all' || activeFilter === 'wildfires')) {
    const fires = liveFeedsData.wildfires.events.slice(0, 15);
    for (const f of fires) {
      const card = document.createElement('div');
      card.className = 'incident-card fire-highlight';
      card.innerHTML = `
        <div class="card-top">
          <span class="tag-badge tag-fire">FIRE</span>
          <span class="time-label">NASA EONET</span>
        </div>
        <div class="card-title-text">${f.title}</div>
        <div class="card-desc-text">Lat: ${Number(f.lat).toFixed(2)}, Lon: ${Number(f.lon).toFixed(2)}</div>
      `;
      card.addEventListener('click', () => {
        if (globeInstance) globeInstance.focusLocation(f.lat, f.lon);
      });
      listEl.appendChild(card);
    }
  }
}

function renderTacticalNetwork() {
  const container = document.getElementById('tactical-svg-container');
  if (!container || !currentExerciseState) return;

  const edges = currentExerciseState.all_roads || [];
  const nodes = currentExerciseState.nodes || [];
  const shelters = currentExerciseState.shelters || [];

  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  const normalEdgeColor = isLight ? '#059669' : '#8df6bc';
  const cutEdgeColor = isLight ? '#dc2626' : '#ff7765';
  const textColor = isLight ? '#0f172a' : '#f5f3ee';
  const nodeFill = isLight ? '#ffffff' : '#111a21';

  let svgHtml = `<svg viewBox="0 0 450 300" style="width:100%; height:100%; max-height:480px;">`;

  // Draw Edges
  for (const e of edges) {
    const u = NODE_SVG_COORDS[e.source];
    const v = NODE_SVG_COORDS[e.target];
    if (!u || !v) continue;

    const isCut = e.status !== 'normal';
    const strokeColor = isCut ? cutEdgeColor : normalEdgeColor;
    const strokeWidth = isCut ? '3.5' : '2.0';
    const dash = isCut ? 'stroke-dasharray="4,3"' : '';

    svgHtml += `
      <line x1="${u.x}" y1="${u.y}" x2="${v.x}" y2="${v.y}" 
            stroke="${strokeColor}" stroke-width="${strokeWidth}" ${dash} opacity="0.85">
        <title>${e.id}: ${e.name} (${e.status})</title>
      </line>
    `;
  }

  // Draw Nodes
  for (const n of nodes) {
    const pos = NODE_SVG_COORDS[n.id];
    if (!pos) continue;

    const hasShelter = shelters.some(s => s.node_id === n.id);
    const strokeColor = hasShelter ? '#f3c56b' : (isLight ? '#2563eb' : '#60a5fa');

    svgHtml += `
      <circle cx="${pos.x}" cy="${pos.y}" r="8" fill="${nodeFill}" stroke="${strokeColor}" stroke-width="2.5">
        <title>${n.id}: ${n.name}</title>
      </circle>
      <text x="${pos.x + 10}" y="${pos.y + 4}" fill="${textColor}" font-size="9" font-family="monospace">${n.id}: ${pos.name}</text>
    `;
  }

  // Draw Highlighted Safe Evacuation Corridor (Gold Route)
  if (activeEvacPath && activeEvacPath.length > 1) {
    for (let i = 0; i < activeEvacPath.length - 1; i++) {
      const u = NODE_SVG_COORDS[activeEvacPath[i]];
      const v = NODE_SVG_COORDS[activeEvacPath[i + 1]];
      if (u && v) {
        svgHtml += `
          <line x1="${u.x}" y1="${u.y}" x2="${v.x}" y2="${v.y}" 
                stroke="#f3c56b" stroke-width="6" opacity="0.9" stroke-linecap="round">
            <animate attributeName="opacity" values="0.9;0.4;0.9" dur="1.8s" repeatCount="indefinite" />
          </line>
        `;
      }
    }
  }

  svgHtml += `</svg>`;
  container.innerHTML = svgHtml;
}

function renderShelterTable(shelters = []) {
  const tbody = document.getElementById('shelter-table-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  for (const s of shelters) {
    const isFull = s.status !== 'open' || s.current_occupancy >= s.max_capacity;
    const tagClass = isFull ? 'tag-danger' : 'tag-success';
    const statusText = isFull ? 'FULL' : `${s.remaining_capacity} left`;

    const row = document.createElement('tr');
    row.innerHTML = `
      <td><strong>${s.name}</strong><div style="font-size:10px; color:var(--ink-muted);">Node ${s.node_id} | H2O: ${s.water_rations_days}d</div></td>
      <td>${s.max_capacity}</td>
      <td>${s.current_occupancy}</td>
      <td><span class="tag-badge ${tagClass}">${statusText}</span></td>
    `;
    tbody.appendChild(row);
  }
}

async function applyJudgeRoadDamage() {
  const roadId = document.getElementById('judge-road-select').value;
  const status = document.getElementById('judge-status-select').value;

  try {
    const resp = await fetch('/api/exercise/road_status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ road_id: roadId, status: status, reason: `Judge injected damage: ${status}` })
    });
    const res = await resp.json();
    if (res.success) {
      appendTrace('critic', `[JUDGE CONTROL] Road ${roadId} set to ${status}. Authoritative revision bumped to #${res.revision}. Recomputing paths...`);
      showStaleBanner();
      await refreshAllData();
      checkEvacuationRoute('N1');
    }
  } catch (err) {
    console.error("Judge cut failed:", err);
  }
}

async function applyJudgeShock(shockType) {
  try {
    const resp = await fetch('/api/exercise/shock', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ shock_type: shockType })
    });
    const res = await resp.json();
    appendTrace('critic', `[OPERATIONAL SHOCK] Injected ${shockType}. Shelters saturated. Revision bumped to #${res.revision}.`);
    showStaleBanner();
    await refreshAllData();
  } catch (err) {
    console.error("Shock failed:", err);
  }
}

async function resetExerciseState() {
  try {
    const resp = await fetch('/api/exercise/reset', { method: 'POST' });
    const res = await resp.json();
    appendTrace('system', `[RESET] Exercise state restored to baseline. Revision: #1.`);
    hideStaleBanner();
    await refreshAllData();
  } catch (err) {
    console.error("Reset failed:", err);
  }
}

function showStaleBanner() {
  const b = document.getElementById('stale-alert-banner');
  if (b) {
    b.style.display = 'block';
    setTimeout(() => { b.style.display = 'none'; }, 6000);
  }
}

function hideStaleBanner() {
  const b = document.getElementById('stale-alert-banner');
  if (b) b.style.display = 'none';
}

async function checkEvacuationRoute(originNode = 'N1') {
  try {
    const resp = await fetch('/api/agent/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        instruction: `Call compute_evacuation_route from origin_node='${originNode}'. If safe route found, report corridor and distance. If blocked or fail closed, report stranded area explicitly.`,
      })
    });
    handleSSEStream(resp);
  } catch (err) {
    console.error("Route check error:", err);
  }
}

function triggerCapabilityDemo(capNum) {
  const prompts = {
    "1": "assess_regional_risk for Vizag Coastal Urban Zone. Report composite risk score and causes.",
    "2": "get_affected_population_aid urgency_filter='critical'. Report trapped count and locations.",
    "3": "audit_road_network. List all blocked or impaired road segments.",
    "4": "query_shelter_capacity. Report open shelters and remaining capacity.",
    "5": "prioritize_rescue_medical. Rank all rescue operations deterministically.",
    "6": "calculate_supply_shortfalls. Identify critical water or medical deficits across shelters.",
    "7": "compute_evacuation_route from origin_node='N1'. Verify road closure invariants and shelter capacity.",
    "8": "simulate_worsening_scenario event_type='aftershock_m5_5'. Evaluate secondary structural vulnerabilities.",
    "9": "recommend_resource_deployment. Map available search and rescue teams to high-priority requests.",
    "10": "Execute top three actions: recommend deployment, compute safe evacuation route, and dispatch top mission.",
  };

  const p = prompts[capNum] || `Execute capability ${capNum}`;
  document.getElementById('agent-user-prompt').value = p;
  submitAgentInstructionWithText(p);
}

function submitAgentInstruction() {
  const input = document.getElementById('agent-user-prompt');
  const text = (input.value || '').trim();
  if (!text) return;
  submitAgentInstructionWithText(text);
}

function submitAgentInstructionWithText(text) {
  appendTrace('user', text);
  startAgentStream(text);
}

async function startAgentStream(instruction) {
  try {
    const resp = await fetch('/api/agent/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        instruction: instruction,
        multi_agent: true,
      })
    });
    handleSSEStream(resp);
  } catch (err) {
    appendTrace('error', `Agent connection error: ${err}`);
  }
}

async function handleSSEStream(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const rawJson = line.slice(6).trim();
        if (!rawJson) continue;
        try {
          const event = JSON.parse(rawJson);
          processAgentEvent(event);
        } catch (e) {
          console.error("SSE parse error:", e);
        }
      }
    }
  }
}

function processAgentEvent(event) {
  if (event.type === 'tool_call') {
    appendTrace('tool', `[TOOL CALL] ${event.tool_name || event.tool}(${JSON.stringify(event.args || event.arguments || {})})`);
  } else if (event.type === 'tool_result' || (event.type === 'tool_call' && event.status === 'success')) {
    appendTrace('tool', `[OBSERVATION] Output received from ${event.tool_name || event.tool}`);
    if (event.output && event.output.safe_route_found !== undefined) {
      updateEvacCard(event.output);
    }
  } else if (event.type === 'critic_audit') {
    const status = event.audit?.approved ? 'APPROVED' : 'REJECTED';
    appendTrace('critic', `[CRITIC AUDIT] ${status}: ${event.audit?.notes || ''}`);
  } else if (event.type === 'final_answer' || event.type === 'thought') {
    if (event.content) {
      appendTrace('assistant', event.content);
    } else if (event.text) {
      appendTrace('assistant', event.text);
    }
  } else if (event.type === 'done') {
    // Refresh data only when agent run concludes to avoid wiping UI mid-sentence
    refreshAllData();
  } else if (event.type === 'error') {
    appendTrace('error', event.message);
  }
}

// Evacuation Route Highlight State
let activeEvacPath = [];

function updateEvacCard(routeResult) {
  const card = document.getElementById('route-status-display');
  if (routeResult.safe_route_found && routeResult.path_nodes) {
    activeEvacPath = routeResult.path_nodes;
  } else {
    activeEvacPath = [];
  }

  // Auto-render route on the tactical graph if open
  renderTacticalNetwork();

  if (!card) return;
  if (routeResult.safe_route_found) {
    card.innerHTML = `
      <span class="tag-badge tag-success" style="align-self:flex-start;">CORRIDOR APPROVED</span>
      <p style="font-size:11px; margin-top:4px;"><strong>Target:</strong> ${routeResult.destination_shelter_name} (${routeResult.destination_shelter_id})</p>
      <p style="font-size:11px;"><strong>Distance:</strong> ${routeResult.distance_km} km | <strong>Path:</strong> ${routeResult.path_nodes.join(' → ')}</p>
      <div style="font-size:10px; color:var(--mint); margin-top:4px; font-weight:700;">ROUTE HIGHLIGHTED ON TACTICAL MAP (Gold Corridor)</div>
      <div style="font-size:10px; color:var(--ink-muted); margin-top:2px;">Invariants Checked: ${routeResult.closure_invariants_checked} closures verified clear.</div>
    `;
  } else {
    card.innerHTML = `
      <span class="tag-badge tag-danger" style="align-self:flex-start;">FAIL-CLOSED: NO SAFE ROUTE</span>
      <p style="font-size:11px; color:var(--coral); margin-top:4px;">${routeResult.reason}</p>
      <div style="font-size:10px; color:var(--amber); margin-top:2px;">ACTION: ${routeResult.action_required || 'Flag stranded area for air rescue.'}</div>
    `;
  }
}

let currentAssistantMsgEl = null;

function appendTrace(role, text) {
  const thread = document.getElementById('chat-messages-thread');
  if (!thread) return;

  // Streaming continuation: if consecutive assistant chunks arrive, append to existing bubble
  if (role === 'assistant' && currentAssistantMsgEl) {
    const body = currentAssistantMsgEl.querySelector('.msg-body');
    if (body) {
      body.innerHTML = formatMarkdown(text);
      thread.scrollTop = thread.scrollHeight;
      return;
    }
  }

  const msgDiv = document.createElement('div');
  msgDiv.className = `chat-message ${role}-message`;

  let author = 'SPIRITUS AGENT';
  let badgeClass = 'badge-assistant';
  let timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  if (role === 'user') {
    author = 'INCIDENT COMMANDER';
    badgeClass = 'badge-user';
    currentAssistantMsgEl = null;
  } else if (role === 'tool') {
    author = 'TOOL OBSERVER';
    badgeClass = 'badge-tool';
  } else if (role === 'critic') {
    author = 'SAFETY CRITIC AUDITOR';
    badgeClass = 'badge-critic';
  } else if (role === 'error') {
    author = 'SYSTEM ERROR';
    badgeClass = 'badge-critic';
  } else if (role === 'assistant') {
    currentAssistantMsgEl = msgDiv;
  }

  msgDiv.innerHTML = `
    <div class="msg-header">
      <span class="msg-badge ${badgeClass}">${author}</span>
      <span class="msg-time">${timeStr}</span>
    </div>
    <div class="msg-body">${formatMarkdown(text)}</div>
  `;

  thread.appendChild(msgDiv);
  thread.scrollTop = thread.scrollHeight;
}

function formatMarkdown(str) {
  if (typeof str !== 'string') str = JSON.stringify(str, null, 2);
  let html = escapeHtml(str);
  // Bold **text**
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Inline code `text`
  html = html.replace(/`(.*?)`/g, '<code>$1</code>');
  // Line break bullets
  html = html.replace(/\n\s*-\s+(.*)/g, '<br>• $1');
  return html;
}

function escapeHtml(str) {
  if (typeof str !== 'string') str = JSON.stringify(str, null, 2);
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function handleItemSelection(data) {
  appendTrace('system', `Selected target on globe: ${data.title || data.id} (${data.category || 'hazard'})`);
  if (data.id === 'VIZAG-EQ-7.1-EX') {
    document.getElementById('btn-mode-exercise').click();
  }
}
