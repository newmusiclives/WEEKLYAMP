// Public site: the mobile menu toggle. Loaded as a file because the CSP blocks inline scripts.
(function () {
  var b = document.querySelector('.menu-toggle'), m = document.getElementById('mobile-menu');
  if (!b || !m) return;
  b.addEventListener('click', function () {
    var open = m.hasAttribute('hidden');
    m.toggleAttribute('hidden', !open);
    b.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
})();

// Copy buttons: <button data-copy="#id"> copies that input's value (or element's text),
// then reads "Copied!" for two seconds.
document.addEventListener('click', function (e) {
  var btn = e.target.closest('[data-copy]');
  if (!btn) return;
  var src = document.querySelector(btn.getAttribute('data-copy'));
  if (!src) return;
  var text = 'value' in src ? src.value : src.textContent.trim();
  var label = btn.textContent;
  function done() {
    btn.textContent = 'Copied!';
    setTimeout(function () { btn.textContent = label; }, 2000);
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done);
  } else if (src.select) {
    src.select();
    document.execCommand('copy');
    done();
  }
});
