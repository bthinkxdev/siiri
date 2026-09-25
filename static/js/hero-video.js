/* Hero banner videos: play only the visible slide, pause off-screen, honour reduced-motion / data-saver. */
(function () {
  'use strict';

  var carousel = document.getElementById('heroCarousel');
  if (!carousel) return;
  var videos = Array.prototype.slice.call(carousel.querySelectorAll('video[data-hero-video]'));
  if (!videos.length) return;

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var connection = navigator.connection || {};
  var saveData = connection.saveData === true;
  var hero = carousel.closest('.hm-hero') || carousel;
  var visible = true;

  function activeVideo() {
    return carousel.querySelector('.carousel-item.active video[data-hero-video]');
  }

  function sync() {
    var active = activeVideo();
    videos.forEach(function (video) {
      if (video === active && visible && !reduceMotion && !saveData) {
        var playing = video.play();
        if (playing && playing.catch) playing.catch(function () { /* autoplay blocked: poster stays */ });
      } else {
        video.pause();
      }
    });
  }

  // let a video slide run one full loop before the carousel moves on (Bootstrap reads data-bs-interval per slide)
  videos.forEach(function (video) {
    video.addEventListener('loadedmetadata', function () {
      var item = video.closest('.carousel-item');
      if (item && isFinite(video.duration)) {
        item.setAttribute('data-bs-interval', String(Math.min(Math.max(video.duration * 1000, 6500), 30000)));
      }
    });
    if (saveData) video.preload = 'none';
  });

  carousel.addEventListener('slid.bs.carousel', sync);
  document.addEventListener('visibilitychange', function () {
    visible = !document.hidden;
    sync();
  });

  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      visible = entries[0].isIntersecting;
      sync();
    }, { threshold: 0.25 }).observe(hero);
  }

  sync();
})();
