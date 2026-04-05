const API_URL = 'http://localhost:8000/api';
const authToken = localStorage.getItem('authToken');
let adminTables = [];

window.onload = async function () {
    await checkAdminAuth();
};

async function checkAdminAuth() {
    const errorDiv = document.getElementById('adminError');
    if (!authToken) {
        window.location.href = '/';
        return;
    }
    try {
        const response = await fetch(`${API_URL}/auth/me`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (!response.ok) {
            throw new Error('Auth failed');
        }
    } catch (error) {
        errorDiv.textContent = 'Session expired. Please login again.';
        setTimeout(() => { window.location.href = '/'; }, 800);
    }
}

function logoutAdmin() {
    localStorage.removeItem('authToken');
    window.location.href = '/';
}

async function loadAdminTables() {
    const button = document.getElementById('adminLoadTablesButton');
    const select = document.getElementById('adminTableSelect');
    const metaDiv = document.getElementById('adminMeta');
    const errorDiv = document.getElementById('adminError');
    const tableView = document.getElementById('adminTableView');
    try {
        button.disabled = true;
        metaDiv.textContent = 'Loading tables...';
        errorDiv.textContent = '';
        const response = await fetch(`${API_URL}/admin/tables`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load tables');
        }
        const rawTables = data.tables || [];
        adminTables = rawTables.map(item => {
            if (typeof item === 'string') {
                return { name: item, columns: [] };
            }
            return item;
        });
        select.innerHTML = '<option value="">Select table</option>' + adminTables
            .map(table => `<option value="${table.name}">${table.name}</option>`)
            .join('');
        metaDiv.textContent = `Loaded ${adminTables.length} tables`;
        tableView.innerHTML = '';
    } catch (error) {
        errorDiv.textContent = error.message || 'Failed to load tables';
    } finally {
        button.disabled = false;
    }
}

async function loadAdminTableRows() {
    const button = document.getElementById('adminLoadRowsButton');
    const select = document.getElementById('adminTableSelect');
    const limitInput = document.getElementById('adminLimitInput');
    const metaDiv = document.getElementById('adminMeta');
    const errorDiv = document.getElementById('adminError');
    const tableView = document.getElementById('adminTableView');
    const tableName = (select.value || '').trim();
    if (!tableName) {
        metaDiv.textContent = 'Please select a table first.';
        return;
    }
    const rawLimit = Number(limitInput.value || 50);
    const limit = Math.min(200, Math.max(1, Number.isFinite(rawLimit) ? rawLimit : 50));
    limitInput.value = String(limit);
    try {
        button.disabled = true;
        metaDiv.textContent = `Loading rows from ${tableName}...`;
        errorDiv.textContent = '';
        tableView.innerHTML = '';
        const response = await fetch(`${API_URL}/admin/tables/${encodeURIComponent(tableName)}/rows?limit=${limit}`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load rows');
        }
        metaDiv.textContent = `${tableName}: ${data.count} rows (limit ${data.limit})`;
        renderAdminRows(data.columns || [], data.rows || []);
    } catch (error) {
        errorDiv.textContent = error.message || 'Failed to load rows';
    } finally {
        button.disabled = false;
    }
}

function renderAdminRows(columns, rows) {
    const tableView = document.getElementById('adminTableView');
    const normalizedColumns = columns.map(col => (typeof col === 'string' ? { name: col, type: '' } : col));
    const columnNames = normalizedColumns.map(col => col.name);
    if (!rows.length) {
        tableView.innerHTML = '<p>No rows found.</p>';
        return;
    }
    const head = columnNames.map(col => `<th>${escapeHtml(col)}</th>`).join('');
    const body = rows.map(row => {
        return `<tr>${columnNames.map(col => `<td>${escapeHtml(formatCell(row[col]))}</td>`).join('')}</tr>`;
    }).join('');
    tableView.innerHTML = `
        <div class="admin-columns-meta">
            ${normalizedColumns.map(col => `<span class="tag">${escapeHtml(`${col.name} (${col.type || 'TEXT'})`)}</span>`).join('')}
        </div>
        <div class="admin-table-wrap">
            <table class="admin-table">
                <thead><tr>${head}</tr></thead>
                <tbody>${body}</tbody>
            </table>
        </div>
    `;
}

function formatCell(value) {
    if (value === null || value === undefined) {
        return '';
    }
    if (typeof value === 'object') {
        return JSON.stringify(value);
    }
    return String(value);
}

function escapeHtml(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}
