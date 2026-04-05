// API Configuration
const API_URL = 'http://localhost:8000/api';

// State
let authToken = localStorage.getItem('authToken');
let currentUser = null;

// Initialize
window.onload = function() {
    if (authToken) {
        checkAuth();
    }
};

// Authentication
async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    const errorDiv = document.getElementById('loginError');
    
    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        if (!response.ok) {
            throw new Error('Login failed');
        }
        
        const data = await response.json();
        authToken = data.access_token;
        localStorage.setItem('authToken', authToken);
        
        errorDiv.textContent = '';
        checkAuth();
        
    } catch (error) {
        errorDiv.textContent = 'Login failed. Please check your credentials.';
    }
}

async function checkAuth() {
    try {
        const response = await fetch(`${API_URL}/auth/me`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Auth failed');
        }
        
        currentUser = await response.json();
        showApp();
        loadResume();
        
    } catch (error) {
        logout();
    }
}

function showApp() {
    document.getElementById('loginSection').style.display = 'none';
    document.getElementById('appSection').style.display = 'block';
    document.getElementById('userInfo').style.display = 'flex';
    document.getElementById('username').textContent = `👤 ${currentUser.username}`;
}

function logout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('authToken');
    
    document.getElementById('loginSection').style.display = 'block';
    document.getElementById('appSection').style.display = 'none';
    document.getElementById('userInfo').style.display = 'none';
    document.getElementById('resumeDisplay').style.display = 'none';
}

// Resume Upload
async function handleUpload(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('resumeFile');
    const file = fileInput.files[0];
    const errorDiv = document.getElementById('uploadError');
    const progressDiv = document.getElementById('uploadProgress');
    
    if (!file) {
        errorDiv.textContent = 'Please select a PDF file';
        return;
    }
    
    if (!file.name.endsWith('.pdf')) {
        errorDiv.textContent = 'Only PDF files are allowed';
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        progressDiv.style.display = 'block';
        errorDiv.textContent = '';
        
        const response = await fetch(`${API_URL}/resume/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            },
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Upload failed');
        }
        
        const data = await response.json();
        progressDiv.style.display = 'none';
        
        document.getElementById('resumeStatus').textContent = 
            `✅ ${data.message} Parsing in progress... Please wait a few seconds and click refresh.`;
        
        // Auto-refresh after 3 seconds
        setTimeout(() => {
            loadResume();
        }, 3000);
        
    } catch (error) {
        progressDiv.style.display = 'none';
        errorDiv.textContent = 'Upload failed. Please try again.';
    }
}

// Load Resume Data
async function loadResume() {
    try {
        const response = await fetch(`${API_URL}/resume/me`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.status === 404) {
            document.getElementById('resumeStatus').textContent = 
                'ℹ️ No resume uploaded yet. Upload your resume to get started!';
            document.getElementById('resumeDisplay').style.display = 'none';
            return;
        }
        
        if (!response.ok) {
            throw new Error('Failed to load resume');
        }
        
        const resume = await response.json();
        displayResume(resume);
        
    } catch (error) {
        console.error('Error loading resume:', error);
    }
}

async function checkAtsScore() {
    const statusDiv = document.getElementById('resumeStatus');
    const errorDiv = document.getElementById('uploadError');
    const button = document.getElementById('atsButton');

    try {
        errorDiv.textContent = '';
        button.disabled = true;
        button.textContent = 'Checking ATS Score...';
        statusDiv.textContent = '🤖 Running AI ATS score check...';

        const response = await fetch(`${API_URL}/resume/me/ats-score`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to check ATS score');
        }

        statusDiv.textContent = `✅ ATS score updated: ${data.resume_score ?? 'N/A'}/100`;
        const atsCheckedDiv = document.getElementById('atsCheckedAt');
        if (data.last_ats_checked_at) {
            atsCheckedDiv.textContent = `Last checked: ${new Date(data.last_ats_checked_at).toLocaleString()}`;
        }
        await loadResume();
    } catch (error) {
        errorDiv.textContent = error.message || 'ATS score check failed. Please try again.';
    } finally {
        button.disabled = false;
        button.textContent = 'Check ATS Score via AI';
    }
}

async function runAutoJobSearch() {
    const statusDiv = document.getElementById('resumeStatus');
    const errorDiv = document.getElementById('uploadError');
    const button = document.getElementById('jobSearchButton');
    const metaDiv = document.getElementById('jobSearchMeta');
    const selectedMode = document.querySelector('input[name="workAuthMode"]:checked')?.value || 'singapore_pr';
    const selectedEmploymentMode = document.querySelector('input[name="employmentMode"]:checked')?.value || 'all';

    try {
        errorDiv.textContent = '';
        button.disabled = true;
        button.textContent = 'Searching...';
        statusDiv.textContent = '🔎 Running bounded parallel job search...';

        const response = await fetch(`${API_URL}/jobs/auto-search`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                location: 'Singapore',
                max_terms: 6,
                per_source_page: 0,
                max_total_requests: 24,
                max_concurrency: 4,
                work_auth_mode: selectedMode,
                employment_mode: selectedEmploymentMode
            })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Auto search failed');
        }

        statusDiv.textContent = `✅ Job search done: ${data.deduped_count} jobs`;
        const sourceCounts = data.source_candidate_counts || {};
        const topCounts = data.top_source_counts || {};
        metaDiv.textContent = `Mode: ${data.work_auth_mode || selectedMode} | Employment: ${data.employment_mode || selectedEmploymentMode} | Requests: ${data.search_requests_planned} | Concurrency: ${data.max_concurrency_used} | Visa filtered: ${data.work_auth_filtered_out || 0} | Employment filtered: ${data.employment_filtered_out || 0} | Sources(candidates): LI ${sourceCounts.linkedin || 0}, Indeed ${sourceCounts.indeed || 0}, Foundit ${sourceCounts.foundit || 0}, GJobs ${sourceCounts.google_jobs || 0} | Top10: LI ${topCounts.linkedin || 0}, Indeed ${topCounts.indeed || 0}, Foundit ${topCounts.foundit || 0}, GJobs ${topCounts.google_jobs || 0}`;
        renderJobs(data.jobs || []);
    } catch (error) {
        errorDiv.textContent = error.message || 'Job search failed. Please try again.';
    } finally {
        button.disabled = false;
        button.textContent = 'Search Jobs Now';
    }
}

function renderJobs(jobs) {
    const jobsDiv = document.getElementById('jobsList');
    if (!jobs || jobs.length === 0) {
        jobsDiv.innerHTML = '<p>No jobs found yet.</p>';
        return;
    }
    jobsDiv.innerHTML = jobs.slice(0, 10).map(job => {
        const score = job.match_score ?? 0;
        const platform = (job.platform || '').toUpperCase();
        const detailUrl = job.detail_url || job.url || '';
        const safeTitle = job.title || 'Unknown role';
        const safeCompany = job.company || 'Unknown';
        const link = detailUrl
            ? `<a href="${detailUrl}" target="_blank" rel="noopener noreferrer" onclick="trackJobView(event, '${encodeURIComponent(detailUrl)}', '${encodeURIComponent(safeTitle)}', '${encodeURIComponent(safeCompany)}')">Open</a>`
            : '';
        return `<p>📌 <strong>${job.title || 'Unknown role'}</strong> @ ${job.company || 'Unknown'} (${platform})<br>📍 ${job.location || 'N/A'} | 🎯 Score: ${score}/100 ${link ? `| ${link}` : ''}</p>`;
    }).join('');
}

async function trackJobView(event, encodedUrl, encodedTitle, encodedCompany) {
    if (event) {
        event.stopPropagation();
    }
    const url = decodeURIComponent(encodedUrl || '');
    const title = decodeURIComponent(encodedTitle || '');
    const company = decodeURIComponent(encodedCompany || '');
    try {
        await fetch(`${API_URL}/jobs/track-view`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url, title, company })
        });
    } catch (error) {
        console.error('Track view failed:', error);
    }
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

// Display Resume Data
function displayResume(resume) {
    const parsed = resume.parsed_data;
    
    // Update stats
    document.getElementById('skillsCount').textContent = parsed.skills.length;
    document.getElementById('searchTermsCount').textContent = resume.search_terms.length;
    document.getElementById('statusBadge').textContent = resume.parsing_status.toUpperCase();
    
    // Contact info
    const contactDiv = document.getElementById('contactInfo');
    if (parsed.contact) {
        contactDiv.innerHTML = `
            ${parsed.contact.email ? `<p>📧 ${parsed.contact.email}</p>` : ''}
            ${parsed.contact.phone ? `<p>📱 ${parsed.contact.phone}</p>` : ''}
            ${parsed.contact.location ? `<p>📍 ${parsed.contact.location}</p>` : ''}
        `;
    } else {
        contactDiv.innerHTML = '<p>No contact information found</p>';
    }
    
    // Skills
    const skillsDiv = document.getElementById('skillsList');
    if (parsed.skills.length > 0) {
        skillsDiv.innerHTML = parsed.skills
            .map(skill => `<span class="tag">${skill}</span>`)
            .join('');
    } else {
        skillsDiv.innerHTML = '<p>No skills extracted yet</p>';
    }
    
    // Search terms
    const searchTermsDiv = document.getElementById('searchTermsList');
    if (resume.search_terms.length > 0) {
        searchTermsDiv.innerHTML = resume.search_terms
            .map(term => `<span class="tag">${term}</span>`)
            .join('');
    } else {
        searchTermsDiv.innerHTML = '<p>No search terms generated yet</p>';
    }
    
    // Companies
    const companiesDiv = document.getElementById('companiesList');
    if (parsed.experience && parsed.experience.length > 0) {
        companiesDiv.innerHTML = parsed.experience
            .map(exp => `<p>🏢 ${exp.company}</p>`)
            .join('');
    } else {
        companiesDiv.innerHTML = '<p>No companies found</p>';
    }

    // Resume score
    const scoreDiv = document.getElementById('resumeScore');
    const atsCheckedDiv = document.getElementById('atsCheckedAt');
    if (parsed.resume_score !== undefined && parsed.resume_score !== null) {
        scoreDiv.innerHTML = `<p>✅ Score: <strong>${parsed.resume_score}/100</strong></p>`;
    } else {
        scoreDiv.innerHTML = '<p>Score not available yet</p>';
    }
    if (parsed.last_ats_checked_at) {
        atsCheckedDiv.textContent = `Last checked: ${new Date(parsed.last_ats_checked_at).toLocaleString()}`;
    } else {
        atsCheckedDiv.textContent = 'Last checked: not yet';
    }

    // Improvement suggestions
    const suggestionsDiv = document.getElementById('improvementSuggestions');
    if (parsed.improvement_suggestions && parsed.improvement_suggestions.length > 0) {
        suggestionsDiv.innerHTML = parsed.improvement_suggestions
            .map(item => `<p>• ${item}</p>`)
            .join('');
    } else {
        suggestionsDiv.innerHTML = '<p>No suggestions available yet</p>';
    }

    // Keep job section stable on resume load
    const jobsDiv = document.getElementById('jobsList');
    if (jobsDiv && !jobsDiv.innerHTML.trim()) {
        jobsDiv.innerHTML = '<p>Click "Search Jobs Now" to fetch ranked jobs.</p>';
    }
    
    // Show the display section
    document.getElementById('resumeDisplay').style.display = 'block';
    document.getElementById('resumeStatus').textContent = 
        `✅ Resume loaded: ${resume.filename} (Uploaded: ${new Date(resume.upload_date).toLocaleDateString()})`;
}
