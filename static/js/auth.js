/* LM Compliance — auth helper.
 * Works in two modes:
 *   1. Normal browser: server session cookie (no JS needed).
 *   2. Sandboxed preview iframe (cookies blocked): a bearer token travels in the URL.
 *      Every internal link gets the token appended; every form submits via fetch with
 *      an X-Auth-Token header so POSTs authenticate too.
 */
(function () {
  'use strict';

  function getToken() {
    // prefer the token currently in the URL (survives reloads, no storage needed)
    var m = location.search.match(/[?&]token=([^&]+)/);
    if (m) return m[1];
    try { return localStorage.getItem('lm_token') || ''; } catch (e) { return ''; }
  }
  var TOKEN = getToken();

  function withToken(url) {
    if (!TOKEN || url.indexOf('token=') !== -1) return url;
    var sep = url.indexOf('?') === -1 ? '?' : '&';
    return url + sep + 'token=' + encodeURIComponent(TOKEN);
  }

  function persist() {
    try { if (TOKEN) localStorage.setItem('lm_token', TOKEN); } catch (e) {}
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!TOKEN) return;
    persist();
    // rewrite internal links
    document.querySelectorAll('a[href]').forEach(function (a) {
      var h = a.getAttribute('href') || '';
      if ((h[0] === '/' || h.indexOf(location.origin) === 0) && h.indexOf('token=') === -1) {
        a.setAttribute('href', withToken(h));
      }
    });
    // rewrite form actions + submit via fetch (keeps the token header on POST)
    document.querySelectorAll('form[method="post"]').forEach(function (f) {
      if (f.dataset.lmHandled) return;
      f.dataset.lmHandled = '1';
      f.addEventListener('submit', function (ev) {
        ev.preventDefault();
        var url = withToken(f.getAttribute('action') || location.pathname);
        var btn = f.querySelector('button[type="submit"]');
        var opts = { method: 'POST', headers: {} };
        if (f.enctype === 'multipart/form-data') {
          opts.body = new FormData(f);
        } else {
          opts.headers['Content-Type'] = 'application/x-www-form-urlencoded';
          opts.body = new URLSearchParams(new FormData(f)).toString();
        }
        if (TOKEN) opts.headers['X-Auth-Token'] = TOKEN;
        if (btn) { btn.disabled = true; btn.textContent = 'Please wait…'; }
        fetch(url, opts).then(function (r) {
          // fetch follows the server's redirect automatically; land on the final URL
          if (r.redirected) { location.href = withToken(r.url); }
          else if (r.ok) { location.reload(); }
          else { location.href = withToken('/'); }
        }).catch(function () {
          if (btn) { btn.disabled = false; btn.textContent = 'Save'; }
          alert('Submission failed — please retry.');
        });
      });
    });
  });

  // logout: clear token, then server logout
  window.lmLogout = function (e) {
    e.preventDefault();
    try { localStorage.removeItem('lm_token'); } catch (err) {}
    location.href = withToken('/logout');
  };
})();
