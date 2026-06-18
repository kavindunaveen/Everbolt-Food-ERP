<script>
// Formatters
const fmtCur = (v) => new Intl.NumberFormat('en-LK', { notation:'compact', compactDisplay:'short' }).format(v);
const fmtFull = (v) => new Intl.NumberFormat('en-LK', { minimumFractionDigits:2, maximumFractionDigits:2 }).format(v);
const fmtNum = (v) => new Intl.NumberFormat('en-US').format(v);

let targetGaugeChart, trendChart, categoryChart, quotationChart;
let currentFrom = null;
let currentTo = null;
let currentAllTime = false;

// Initialize empty charts
function initCharts() {
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.color = '#64748b';

    // Target Gauge
    const ctxGauge = document.getElementById('targetGaugeChart').getContext('2d');
    targetGaugeChart = new Chart(ctxGauge, {
        type: 'doughnut',
        data: { labels: ['Achieved', 'Remaining'], datasets: [{ data:[0, 100], backgroundColor:['#4f46e5', '#f1f5f9'], borderWidth:0 }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            rotation: -90, circumference: 180, cutout: '80%',
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            animation: { duration: 1000 }
        }
    });

    // Trend Line Chart
    const ctxTrend = document.getElementById('trendChart').getContext('2d');
    trendChart = new Chart(ctxTrend, {
        type: 'line',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => ` Sales: Rs ${fmtFull(ctx.parsed.y)}` } }
            },
            scales: {
                y: { beginAtZero: true, grid: { borderDash: [4,4] }, ticks: { callback: v => fmtCur(v) } },
                x: { grid: { display: false } }
            },
            elements: {
                line: { tension: 0.4, borderWidth: 3 },
                point: { radius: 4, hoverRadius: 6 }
            }
        }
    });

    // Category Doughnut Chart
    const ctxCat = document.getElementById('categoryChart').getContext('2d');
    categoryChart = new Chart(ctxCat, {
        type: 'doughnut',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true, maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: { position: 'right', labels: { boxWidth: 12, usePointStyle: true, font: { size: 11, weight: '600' } } }
            }
        }
    });

    // Quotation Chart (Bar)
    const ctxQuot = document.getElementById('quotationChart').getContext('2d');
    quotationChart = new Chart(ctxQuot, {
        type: 'bar',
        data: { labels: ['Sent', 'Accepted', 'Rejected'], datasets: [{ data: [0,0,0], backgroundColor: ['#6366f1', '#10b981', '#f43f5e'], borderRadius: 4 }] },
        options: {
            indexAxis: 'y',
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { beginAtZero: true, grid: { display: false } },
                y: { grid: { display: false }, ticks: { font: { weight: 'bold' } } }
            }
        }
    });
}

async function loadData(dateFrom, dateTo, allTime, btnEl = null) {
    // Update active button styling
    if (btnEl) {
        document.querySelectorAll('.time-filter').forEach(el => {
            el.classList.remove('bg-indigo-600', 'text-white', 'shadow-sm', 'active-filter');
            el.classList.add('bg-white', 'text-gray-600');
        });
        btnEl.classList.remove('bg-white', 'text-gray-600');
        btnEl.classList.add('bg-indigo-600', 'text-white', 'shadow-sm', 'active-filter');
    }

    currentFrom = dateFrom;
    currentTo = dateTo;
    currentAllTime = allTime;

    const spId = document.getElementById('salespersonSelect').value;
    
    let url = `/dashboard/api/salesperson/?salesperson_id=${spId}&`;
    if (allTime) url += `all_time=true&`;
    else {
        if (dateFrom) url += `date_from=${dateFrom}&`;
        if (dateTo) url += `date_to=${dateTo}&`;
    }

    document.getElementById('lastUpdated').innerText = 'Fetching...';
    try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('Network response was not ok');
        const data = await resp.json();
        
        document.getElementById('lastUpdated').innerText = `Live at ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;

        // Top KPIs
        document.getElementById('kpi-sales').innerText = `Rs ${fmtCur(data.overview.sales)}`;
        document.getElementById('kpi-invoices').innerText = fmtNum(data.overview.invoices);
        document.getElementById('kpi-customers').innerText = fmtNum(data.overview.new_customers);
        
        if (data.overview.prediction > 0 && !allTime) {
            document.getElementById('kpi-prediction').innerText = `Rs ${fmtCur(data.overview.prediction)}`;
        } else {
            document.getElementById('kpi-prediction').innerText = '—';
        }

        // Target Gauge
        const target = data.targets.target;
        const achieved = data.overview.sales;
        document.getElementById('text-target').innerText = data.targets.has_target ? `Rs ${fmtCur(target)}` : 'N/A';
        document.getElementById('text-achieved').innerText = `Rs ${fmtCur(achieved)}`;

        if (data.targets.has_target && target > 0) {
            const pct = Math.min((achieved / target) * 100, 100);
            const rem = Math.max(target - achieved, 0);
            targetGaugeChart.data.datasets[0].data = [achieved, rem];
            targetGaugeChart.data.datasets[0].backgroundColor[0] = '#4f46e5';
            document.getElementById('gauge-val').innerText = `${pct.toFixed(1)}%`;
            document.getElementById('gauge-sub').innerText = `Target: Rs ${fmtCur(target)}`;
        } else {
            targetGaugeChart.data.datasets[0].data = [0, 100];
            targetGaugeChart.data.datasets[0].backgroundColor[0] = '#cbd5e1';
            document.getElementById('gauge-val').innerText = 'N/A';
            document.getElementById('gauge-sub').innerText = 'No Target Assigned';
        }
        targetGaugeChart.update();

        // Trend Chart
        trendChart.data.labels = data.trends.labels;
        trendChart.data.datasets = [{
            label: 'Sales Revenue',
            data: data.trends.sales,
            borderColor: '#4f46e5',
            backgroundColor: 'rgba(79, 70, 229, 0.1)',
            fill: true
        }];
        trendChart.update();

        // Category Chart
        const catLabels = data.category_breakdown.map(c => c.category);
        const catData = data.category_breakdown.map(c => c.qty);
        // Palette
        const palette = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];
        categoryChart.data.labels = catLabels;
        categoryChart.data.datasets = [{
            data: catData,
            backgroundColor: palette.slice(0, catLabels.length)
        }];
        categoryChart.update();

        // Quotations
        document.getElementById('quot-total').innerText = data.quotations.total;
        document.getElementById('quot-won').innerText = data.quotations.won;
        document.getElementById('quot-lost').innerText = data.quotations.lost;

        quotationChart.data.datasets[0].data = [data.quotations.total, data.quotations.won, data.quotations.lost];
        quotationChart.update();

    } catch (err) {
        console.error("Error loading dashboard data:", err);
        document.getElementById('lastUpdated').innerText = 'Error loading data';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    
    const urlParams = new URLSearchParams(window.location.search);
    const dateFrom = urlParams.get('date_from') || '';
    const dateTo   = urlParams.get('date_to') || '';
    const allTime  = urlParams.get('all_time') === 'true';

    // Highlight the correct quick month if it matches the URL
    if (dateFrom && dateTo && !allTime) {
        let matched = false;
        document.querySelectorAll('.time-filter').forEach(el => {
            const elClick = el.getAttribute('onclick');
            if (elClick && elClick.includes(dateFrom) && elClick.includes(dateTo)) {
                el.classList.remove('bg-white', 'text-gray-600');
                el.classList.add('bg-indigo-600', 'text-white', 'shadow-sm', 'active-filter');
                matched = true;
            } else {
                el.classList.remove('bg-indigo-600', 'text-white', 'shadow-sm', 'active-filter');
                el.classList.add('bg-white', 'text-gray-600');
            }
        });
        loadData(dateFrom, dateTo, false);
    } else if (allTime) {
        document.querySelectorAll('.time-filter').forEach(el => {
            if (el.dataset.filter === 'all') {
                el.classList.remove('bg-white', 'text-gray-600');
                el.classList.add('bg-indigo-600', 'text-white', 'shadow-sm', 'active-filter');
            } else {
                el.classList.remove('bg-indigo-600', 'text-white', 'shadow-sm', 'active-filter');
                el.classList.add('bg-white', 'text-gray-600');
            }
        });
        loadData(null, null, true);
    } else {
        // Default load first month
        const defaultBtn = document.querySelector('.time-filter[data-filter!="all"]');
        if (defaultBtn) {
            defaultBtn.click();
        } else {
            loadData(null, null, true);
        }
    }

    // Handle salesperson change by redirecting to preserve URL state
    document.getElementById('salespersonSelect')?.addEventListener('change', (e) => {
        const params = new URLSearchParams(window.location.search);
        params.set('salesperson_id', e.target.value);
        window.location.search = params.toString();
    });
});
</script>
