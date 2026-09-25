/* Silent looping background videos ([data-autoplay-video]): play only while on screen, and keep the still
   cover image for visitors who prefer reduced motion or have data-saver on. */
(function () {
  'use strict';

  var videos = Array.prototype.slice.call(document.querySelectorAll('video[data-autoplay-video]'));
  if (!videos.length) return;

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var connection = navigator.connection || {};
  var allowed = !reduceMotion && connection.saveData !== true;

  function play(video) {
    if (!allowed) return;
    video.muted = true;
    var attempt = video.play();
    if (attempt && attempt.catch) attempt.catch(function () { /* autoplay blocked: the cover image stays */ });
  }

  videos.forEach(function (video) {
    video.muted = true;
    if (!allowed) {
      video.pause();
      video.removeAttribute('autoplay');
      video.preload = 'none';
    }

    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) play(video);
          else video.pause();
        });
      }, { threshold: 0.25 }).observe(video);
    } else {
      play(video);
    }
  });

  document.addEventListener('visibilitychange', function () {
    videos.forEach(function (video) {
      if (document.hidden) video.pause();
      else if (allowed) play(video);
    });
  });
})();
