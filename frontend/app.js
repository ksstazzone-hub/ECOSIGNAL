(async function () {
  const formatList = (items) => (Array.isArray(items) ? items : []).map((item) => `<li>${item}</li>`).join('');

  const health = await fetch('/health').then((r) => r.json()).catch(() => ({ status: 'offline' }));
  const status = document.getElementById('status-pill');
  status.textContent = health.status === 'ok' ? 'Sistema activo' : 'Sin conexión';
  status.style.color = health.status === 'ok' ? '#6ee7b7' : '#fbbf24';
  status.style.background = health.status === 'ok' ? 'rgba(110, 231, 183, 0.12)' : 'rgba(245, 158, 11, 0.12)';
  status.style.borderColor = health.status === 'ok' ? 'rgba(110, 231, 183, 0.3)' : 'rgba(245, 158, 11, 0.3)';
  document.getElementById('health-status').innerHTML = `
    <p><strong>Estado:</strong> ${health.status || 'desconocido'}</p>
    <p><strong>Plataforma:</strong> ${health.platform || 'ECOSIGNAL'}</p>
    <p>La ausencia de datos no equivale a estabilidad ecológica.</p>
  `;

  const ecosystemResponse = await fetch('/api/ecosystems').then((r) => r.json()).catch(() => ({ ecosystem_categories: [] }));
  const ecosystems = Array.isArray(ecosystemResponse) ? ecosystemResponse : ecosystemResponse.ecosystem_categories || [];
  document.getElementById('ecosystems').innerHTML = `
    <div class="badge-row">
      ${ecosystems.map((item) => `<span class="badge">${item}</span>`).join('')}
    </div>
  `;

  const connectors = await fetch('/api/connectors').then((r) => r.json()).catch(() => ({}));
  const connectorEntries = Object.entries(connectors || {});
  const connectorHtml = connectorEntries.length
    ? connectorEntries.map(([key, value]) => `
        <li><strong>${value.label || key}</strong> — ${value.provider || 'Proveedor'}<br>${value.coverage?.summary || 'Cobertura variable'}</li>
      `).join('')
    : '<li>No se pudieron cargar los conectores del sistema.</li>';
  document.getElementById('connectors').innerHTML = `<ul>${connectorHtml}</ul>`;

  const coverage = await fetch('/api/coverage').then((r) => r.json()).catch(() => ({ message: 'Sin información disponible' }));
  document.getElementById('coverage').innerHTML = `
    <ul>
      <li><strong>Suficiente:</strong> áreas con datos suficientes para revisión.</li>
      <li><strong>Limitada:</strong> datos parciales o incompletos.</li>
      <li><strong>Sin datos:</strong> ausencia de registros no implica estabilidad.</li>
      <li><strong>Monitoreo:</strong> regiones bajo observación activa.</li>
    </ul>
    <p>${coverage.message || 'Cobertura contextualizada y explícita.'}</p>
  `;

  const analysisResponse = await fetch('/api/analytic-modules').then((r) => r.json()).catch(() => ({ modules: {} }));
  const modules = analysisResponse.modules || {};
  const moduleList = Object.entries(modules).slice(0, 6).map(([key, value]) => `
    <li><strong>${key}</strong> — ${Array.isArray(value.methods) ? value.methods.join(', ') : 'métodos declarados'}</li>
  `).join('');
  document.getElementById('adaptive-analysis').innerHTML = `<ul>${moduleList || '<li>No hay módulos disponibles.</li>'}</ul>`;
})();
