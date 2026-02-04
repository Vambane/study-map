/**
 * Analytics – Chart.js charts
 */

Chart.defaults.font.family = 'Inter, sans-serif';
Chart.defaults.font.size = 12;
Chart.defaults.color = '#6b6b76';
Chart.defaults.plugins.legend.display = false;

var COLORS = {
    purple: '#8b5cf6',
    purpleLight: '#a78bfa',
    coral: '#ef6c4e',
    teal: '#5bb8a9',
    rose: '#f43f5e',
    amber: '#f59e0b'
};

var tooltipStyle = {
    backgroundColor: '#ffffff',
    titleColor: '#0f0f0f',
    bodyColor: '#6b6b76',
    borderColor: '#e8e8ec',
    borderWidth: 1,
    padding: 12,
    displayColors: false
};

document.addEventListener('DOMContentLoaded', function () {
    if (!document.getElementById('activityChart')) return;

    fetch('/api/analytics-data')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            renderActivity(data.activity);
            renderSkills(data.skills);
            renderComplexity(data.complexity);
            renderDomains(data.domains);
        })
        .catch(function (err) { console.error('Analytics error:', err); });
});

function renderActivity(data) {
    new Chart(document.getElementById('activityChart'), {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Entries',
                data: data.data,
                backgroundColor: 'rgba(139,92,246,0.1)',
                borderColor: COLORS.purple,
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBackgroundColor: COLORS.purple
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: { display: true, text: 'Learning Activity', font: { size: 16, weight: 'bold' }, color: '#0f0f0f', padding: { bottom: 16 } },
                tooltip: tooltipStyle
            },
            scales: {
                y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: 'rgba(0,0,0,0.05)' } },
                x: { grid: { display: false } }
            }
        }
    });
}

function renderSkills(data) {
    if (!data.labels.length) return;
    new Chart(document.getElementById('skillsChart'), {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Count',
                data: data.data,
                backgroundColor: COLORS.purple,
                borderRadius: 8,
                barThickness: 24
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            plugins: {
                title: { display: true, text: 'Top Skills', font: { size: 16, weight: 'bold' }, color: '#0f0f0f', padding: { bottom: 16 } },
                tooltip: tooltipStyle
            },
            scales: {
                x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: 'rgba(0,0,0,0.05)' } },
                y: { grid: { display: false } }
            }
        }
    });
}

function renderComplexity(data) {
    if (!data.labels.length) return;
    var colorMap = { beginner: COLORS.teal, intermediate: COLORS.coral, advanced: COLORS.rose };
    var colors = data.labels.map(function (l) { return colorMap[l.toLowerCase()] || COLORS.purple; });

    new Chart(document.getElementById('complexityChart'), {
        type: 'doughnut',
        data: {
            labels: data.labels.map(function (l) { return l.charAt(0).toUpperCase() + l.slice(1); }),
            datasets: [{ data: data.data, backgroundColor: colors, borderWidth: 0, hoverOffset: 8 }]
        },
        options: {
            responsive: true,
            cutout: '55%',
            plugins: {
                title: { display: true, text: 'Complexity Distribution', font: { size: 16, weight: 'bold' }, color: '#0f0f0f', padding: { bottom: 16 } },
                legend: { display: true, position: 'bottom', labels: { padding: 16, usePointStyle: true, pointStyle: 'circle' } },
                tooltip: tooltipStyle
            }
        }
    });
}

function renderDomains(data) {
    if (!data.labels.length) return;
    new Chart(document.getElementById('domainsChart'), {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Count',
                data: data.data,
                backgroundColor: COLORS.teal,
                borderRadius: 8,
                barThickness: 40
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: { display: true, text: 'Domain Breakdown', font: { size: 16, weight: 'bold' }, color: '#0f0f0f', padding: { bottom: 16 } },
                tooltip: tooltipStyle
            },
            scales: {
                y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: 'rgba(0,0,0,0.05)' } },
                x: { grid: { display: false } }
            }
        }
    });
}
