// /license: the Monthly/Annual billing toggle. A file, not inline, because the CSP blocks inline scripts.
(function () {
    var toggle = document.getElementById('billingToggle');
    var labelMonthly = document.getElementById('labelMonthly');
    var labelAnnual = document.getElementById('labelAnnual');
    function setBilling(annual) {
        toggle.classList.toggle('annual', annual);
        toggle.setAttribute('aria-checked', annual ? 'true' : 'false');
        labelMonthly.classList.toggle('active', !annual);
        labelAnnual.classList.toggle('active', annual);
        var key = annual ? 'annual' : 'monthly';
        document.querySelectorAll('.price-amount, .price-period').forEach(function (el) {
            el.innerHTML = el.getAttribute('data-' + key);
        });
    }
    toggle.addEventListener('click', function () {
        setBilling(!toggle.classList.contains('annual'));
    });
    toggle.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setBilling(!toggle.classList.contains('annual'));
        }
    });
})();
