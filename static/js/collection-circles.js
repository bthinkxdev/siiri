(function () {
  'use strict';

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function init(root) {
    var track = root.querySelector('[data-circles-track]');
    var prev = root.querySelector('[data-circles-prev]');
    var next = root.querySelector('[data-circles-next]');
    if (!track || !prev || !next) return;
    var frame = 0;

    function update() {
      frame = 0;
      var max = track.scrollWidth - track.clientWidth;
      var scrollable = max > 1;
      root.classList.toggle('is-scrollable', scrollable);
      prev.disabled = !scrollable || track.scrollLeft <= 1;
      next.disabled = !scrollable || track.scrollLeft >= max - 1;
    }

    function schedule() {
      if (!frame) frame = window.requestAnimationFrame(update);
    }

    function step(direction) {
      track.scrollBy({ left: direction * Math.max(track.clientWidth * 0.8, 100), behavior: reduceMotion ? 'auto' : 'smooth' });
    }

    prev.addEventListener('click', function () { step(-1); });
    next.addEventListener('click', function () { step(1); });
    track.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    Array.prototype.forEach.call(track.querySelectorAll('img'), function (img) {
      if (!img.complete) img.addEventListener('load', schedule);
    });
    update();
  }

  function boot() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-circles]'), init);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
