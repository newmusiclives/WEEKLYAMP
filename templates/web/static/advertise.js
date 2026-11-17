// /advertise: the campaign estimator. Cost follows the rate card (CPM per issue,
// less the package discount); opens, clicks and sales come from the visitor's
// own assumptions. A file, not inline, because the CSP blocks inline scripts.
(function () {
  var root = document.querySelector('.estimator');
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var num = function (id) { var v = parseFloat($(id).value); return isFinite(v) && v > 0 ? v : 0; };
  var whole = function (n) { return Math.round(n).toLocaleString('en-US'); };
  var money = function (n) {
    var abs = Math.abs(n), s = '$' + abs.toLocaleString('en-US', { minimumFractionDigits: abs < 10 ? 2 : 0, maximumFractionDigits: abs < 10 ? 2 : 0 });
    return n < 0 ? '−' + s : s;
  };
  var discounts = { 1: 1, 3: parseFloat(root.dataset.weeklyDiscount), 12: parseFloat(root.dataset.monthlyDiscount) };

  function update() {
    var list = num('est-list'), cpm = num('est-cpm'), issues = parseInt($('est-package').value, 10);
    var cost = list / 1000 * cpm * issues * (discounts[issues] || 1);
    var sends = list * issues;
    var opens = sends * num('est-open') / 100;
    var clicks = opens * num('est-click') / 100;
    var customers = clicks * num('est-conv') / 100;
    var revenue = customers * num('est-value');
    var net = revenue - cost;

    $('est-issues').textContent = issues + (issues === 1 ? ' issue' : ' issues');
    $('est-cost').textContent = money(cost);
    $('est-sends').textContent = whole(sends);
    $('est-opens').textContent = whole(opens);
    $('est-clicks').textContent = whole(clicks);
    $('est-cpc').textContent = clicks >= 1 ? money(cost / clicks) : '—';
    $('est-customers').textContent = customers >= 10 ? whole(customers) : customers.toFixed(1);
    $('est-revenue').textContent = money(revenue);
    var netEl = $('est-net');
    netEl.textContent = money(net);
    netEl.className = net < 0 ? 'neg' : 'pos';
  }

  // "Try N in the estimator" buttons on the worked examples.
  document.querySelectorAll('.ex-load').forEach(function (btn) {
    btn.addEventListener('click', function () {
      $('est-list').value = btn.dataset.list;
      $('est-cpm').selectedIndex = 0;
      $('est-package').value = '3';
      update();
    });
  });

  root.addEventListener('input', update);
  root.addEventListener('change', update);
  update();
})();
