/* Homepage memories gallery: snap-scrolling row with one focused (centred) photo. */
(function () {
  'use strict';

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function init(root) {
    var track = root.querySelector('[data-memories-track]');
    if (!track) return;
    var items = Array.prototype.slice.call(track.children);
    var prev = root.querySelector('[data-memories-prev]');
    var next = root.querySelector('[data-memories-next]');
    var dashes = Array.prototype.slice.call(root.querySelectorAll('[data-memories-dash]'));
    var frame = 0;
    var current = -1;

    function centerIndex() {
      var mid = track.scrollLeft + track.clientWidth / 2;
      var best = 0;
      var bestDistance = Infinity;
      items.forEach(function (item, i) {
        var distance = Math.abs(item.offsetLeft + item.offsetWidth / 2 - mid);
        if (distance < bestDistance) {
          bestDistance = distance;
          best = i;
        }
      });
      return best;
    }

    function paint() {
      frame = 0;
      var c = centerIndex();
      if (c === current) return;
      current = c;
      items.forEach(function (item, i) {
        item.dataset.dist = String(Math.min(Math.abs(i - c), 3));
      });
      dashes.forEach(function (dash, i) {
        dash.classList.toggle('is-active', i === c);
        dash.setAttribute('aria-current', i === c ? 'true' : 'false');
      });
      if (prev) prev.disabled = c === 0;
      if (next) next.disabled = c === items.length - 1;
    }

    function schedule() {
      if (!frame) frame = window.requestAnimationFrame(paint);
    }

    function go(index, instant) {
      var i = Math.max(0, Math.min(items.length - 1, index));
      var item = items[i];
      track.scrollTo({
        left: item.offsetLeft + item.offsetWidth / 2 - track.clientWidth / 2,
        behavior: instant || reduceMotion ? 'auto' : 'smooth'
      });
    }

    track.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', function () {
      go(current < 0 ? 0 : current, true);
      current = -1;
      schedule();
    });
    if (prev) prev.addEventListener('click', function () { go(centerIndex() - 1); });
    if (next) next.addEventListener('click', function () { go(centerIndex() + 1); });
    dashes.forEach(function (dash, i) {
      dash.addEventListener('click', function () { go(i); });
    });
    track.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowLeft') { event.preventDefault(); go(centerIndex() - 1); }
      if (event.key === 'ArrowRight') { event.preventDefault(); go(centerIndex() + 1); }
    });

    root.classList.add('is-ready');
    // start on the middle photo, like a focused carousel
    go(Math.floor((items.length - 1) / 2), true);
    schedule();
  }

  Array.prototype.forEach.call(document.querySelectorAll('[data-memories]'), init);
})();
