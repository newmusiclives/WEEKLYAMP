function fmt(n) { return '$' + n.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}); }
function fmtDec(n) { return '$' + n.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}); }

function calculate() {
    var subs = parseInt(document.getElementById('slider-subs').value);
    var editions = parseInt(document.getElementById('slider-editions').value);
    var issuesPerWeek = parseInt(document.getElementById('slider-issues').value);
    var cpm = parseFloat(document.getElementById('slider-cpm').value);
    var fillRate = parseFloat(document.getElementById('slider-fill').value) / 100;
    var slots = parseInt(document.getElementById('slider-slots').value);
    var proPrice = parseFloat(document.getElementById('slider-pro-price').value);
    var premPrice = parseFloat(document.getElementById('slider-prem-price').value);
    var proConv = parseFloat(document.getElementById('slider-pro-conv').value) / 100;
    var premConv = parseFloat(document.getElementById('slider-prem-conv').value) / 100;
    var licensees = parseInt(document.getElementById('slider-licensees').value);
    var licenseFee = parseFloat(document.getElementById('slider-license-fee').value);
    var revShare = parseFloat(document.getElementById('slider-rev-share').value) / 100;
    var licenseeRev = parseFloat(document.getElementById('slider-licensee-rev').value);
    var affPer1k = parseFloat(document.getElementById('slider-aff').value);

    // Update display values
    document.getElementById('val-subs').textContent = subs.toLocaleString();
    document.getElementById('val-editions').textContent = editions;
    document.getElementById('val-issues').textContent = issuesPerWeek;
    document.getElementById('val-cpm').textContent = '$' + cpm;
    document.getElementById('val-fill').textContent = (fillRate * 100) + '%';
    document.getElementById('val-slots').textContent = slots;
    document.getElementById('val-pro-price').textContent = fmtDec(proPrice);
    document.getElementById('val-prem-price').textContent = fmtDec(premPrice);
    document.getElementById('val-pro-conv').textContent = (proConv * 100) + '%';
    document.getElementById('val-prem-conv').textContent = (premConv * 100) + '%';
    document.getElementById('val-licensees').textContent = licensees;
    document.getElementById('val-license-fee').textContent = fmt(licenseFee);
    document.getElementById('val-rev-share').textContent = (revShare * 100) + '%';
    document.getElementById('val-licensee-rev').textContent = fmt(licenseeRev);
    document.getElementById('val-aff').textContent = fmt(affPer1k);

    // Calculate
    var totalSubs = subs * editions;
    var issuesPerMonth = issuesPerWeek * 4.33 * editions;
    var totalSlots = issuesPerMonth * slots;
    var filledSlots = Math.round(totalSlots * fillRate);

    // Sponsor revenue
    var sponsorPerSlot = cpm * (subs / 1000) * 1.07;
    var sponsorRevenue = filledSlots * sponsorPerSlot;

    // Paid tiers
    var proSubs = Math.round(totalSubs * proConv);
    var premSubs = Math.round(totalSubs * premConv);
    var tierMRR = (proSubs * proPrice) + (premSubs * premPrice);

    // Affiliates
    var affiliateRevenue = (totalSubs / 1000) * affPer1k;

    // Licensing
    var licenseFees = licensees * licenseFee;
    var licenseShare = licensees * licenseeRev * revShare;

    // Total
    var totalMonthly = sponsorRevenue + tierMRR + affiliateRevenue + licenseFees + licenseShare;
    var annualRevenue = totalMonthly * 12;
    var revPerSub = totalSubs > 0 ? totalMonthly / totalSubs : 0;
    var revPerIssue = issuesPerMonth > 0 ? totalMonthly / issuesPerMonth : 0;

    // Update results
    document.getElementById('total-revenue').textContent = fmt(Math.round(totalMonthly));
    document.getElementById('annual-revenue').textContent = 'Annual: ' + fmt(Math.round(annualRevenue));
    document.getElementById('rev-sponsor').textContent = fmt(Math.round(sponsorRevenue));
    document.getElementById('rev-tiers').textContent = fmt(Math.round(tierMRR));
    document.getElementById('rev-affiliate').textContent = fmt(Math.round(affiliateRevenue));
    document.getElementById('rev-license-fees').textContent = fmt(Math.round(licenseFees));
    document.getElementById('rev-license-share').textContent = fmt(Math.round(licenseShare));

    // Metrics
    document.getElementById('metric-total-subs').textContent = totalSubs.toLocaleString();
    document.getElementById('metric-total-issues').textContent = Math.round(issuesPerMonth);
    document.getElementById('metric-rev-per-sub').textContent = fmtDec(revPerSub);
    document.getElementById('metric-rev-per-issue').textContent = fmt(Math.round(revPerIssue));
    document.getElementById('metric-pro-subs').textContent = proSubs.toLocaleString();
    document.getElementById('metric-prem-subs').textContent = premSubs.toLocaleString();
    document.getElementById('metric-total-slots').textContent = Math.round(totalSlots);
    document.getElementById('metric-filled-slots').textContent = filledSlots;

    // Revenue bars
    var maxRev = Math.max(sponsorRevenue, tierMRR, affiliateRevenue, licenseFees + licenseShare, 1);
    var barsHtml = '';
    var items = [
        {label: 'Sponsors', value: sponsorRevenue, color: '#e8645a'},
        {label: 'Paid Tiers', value: tierMRR, color: '#7c5cfc'},
        {label: 'Affiliates', value: affiliateRevenue, color: '#10b981'},
        {label: 'Licensing', value: licenseFees + licenseShare, color: '#f59e0b'},
    ];
    for (var i = 0; i < items.length; i++) {
        var pct = (items[i].value / maxRev) * 100;
        barsHtml += '<div style="margin-bottom:12px;">';
        barsHtml += '<div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px;"><span>' + items[i].label + '</span><span style="font-weight:700;">' + fmt(Math.round(items[i].value)) + '</span></div>';
        barsHtml += '<div style="background:#e5e7eb;border-radius:8px;height:12px;overflow:hidden;"><div style="background:' + items[i].color + ';height:100%;width:' + pct + '%;border-radius:8px;transition:width 0.3s;"></div></div>';
        barsHtml += '</div>';
    }
    document.getElementById('revenue-bars').innerHTML = barsHtml;

    // Growth projections
    var projHtml = '';
    var cumulative = 0;
    var growthRate = 1.10;
    for (var m = 1; m <= 12; m++) {
        var projSubs = Math.round(totalSubs * Math.pow(growthRate, m - 1));
        var projRev = (sponsorRevenue * Math.pow(growthRate, m - 1)) + tierMRR * Math.pow(growthRate, m - 1) + affiliateRevenue * Math.pow(growthRate, m - 1) + licenseFees + licenseShare;
        cumulative += projRev;
        projHtml += '<tr><td>Month ' + m + '</td><td>' + projSubs.toLocaleString() + '</td><td>' + fmt(Math.round(projRev)) + '</td><td>' + fmt(Math.round(cumulative)) + '</td></tr>';
    }
    document.getElementById('projection-table').innerHTML = projHtml;
}

// Attach event listeners to all sliders
document.addEventListener('DOMContentLoaded', function() {
    var sliderIds = [
        'slider-subs', 'slider-editions', 'slider-issues',
        'slider-cpm', 'slider-fill', 'slider-slots',
        'slider-pro-price', 'slider-prem-price', 'slider-pro-conv', 'slider-prem-conv',
        'slider-licensees', 'slider-license-fee', 'slider-rev-share', 'slider-licensee-rev',
        'slider-aff'
    ];
    for (var i = 0; i < sliderIds.length; i++) {
        var el = document.getElementById(sliderIds[i]);
        if (el) {
            el.addEventListener('input', calculate);
        }
    }
    calculate();
});
