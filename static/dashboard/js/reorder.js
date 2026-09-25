/* Dashboard: drag-and-drop row reordering. The table carries data-reorder-url and data-csrf;
   each row carries data-reorder-id. Works with mouse and touch (pointer events) and the keyboard. */
(function () {
  'use strict';

  var table = document.querySelector('[data-reorder-url]');
  if (!table || !table.tBodies.length) return;

  var body = table.tBodies[0];
  var url = table.getAttribute('data-reorder-url');
  var csrf = table.getAttribute('data-csrf');
  var statusEl = document.getElementById('reorderStatus');
  var saveTimer = 0;
  var drag = null;

  function rows() {
    return Array.prototype.slice.call(body.querySelectorAll('tr[data-reorder-id]'));
  }

  function ids() {
    return rows().map(function (row) { return Number(row.getAttribute('data-reorder-id')); });
  }

  var saved = ids();

  function say(message, kind) {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.className = 'small mb-2 text-' + (kind || 'secondary');
  }

  function same(a, b) {
    return a.length === b.length && a.every(function (value, i) { return value === b[i]; });
  }

  function restore(order) {
    var byId = {};
    rows().forEach(function (row) { byId[row.getAttribute('data-reorder-id')] = row; });
    order.forEach(function (id) { body.appendChild(byId[id]); });
  }

  function save() {
    window.clearTimeout(saveTimer);
    var order = ids();
    if (same(order, saved)) return;
    say('Saving…');
    fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ order: order })
    }).then(function (response) {
      if (response.status === 409) {
        say('The list changed elsewhere. Reloading…', 'warning');
        window.setTimeout(function () { window.location.reload(); }, 900);
        return null;
      }
      if (!response.ok) throw new Error('save failed');
      saved = order;
      say('Order saved. The storefront now shows the new order.', 'success');
      return null;
    }).catch(function () {
      restore(saved);
      say('Could not save the new order. It has been put back; please try again.', 'danger');
    });
  }

  function saveSoon() {
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(save, 500);
  }

  // ---- pointer drag (mouse + touch) from the handle
  body.addEventListener('pointerdown', function (event) {
    var handle = event.target.closest('[data-reorder-handle]');
    if (!handle || (event.pointerType === 'mouse' && event.button !== 0)) return;
    var row = handle.closest('tr');
    event.preventDefault();
    drag = { row: row, handle: handle, pointerId: event.pointerId };
    row.classList.add('is-dragging');
    handle.setPointerCapture(event.pointerId);
  });

  body.addEventListener('pointermove', function (event) {
    if (!drag || event.pointerId !== drag.pointerId) return;
    var y = event.clientY;
    var others = rows().filter(function (row) { return row !== drag.row; });
    var before = null;
    for (var i = 0; i < others.length; i += 1) {
      var box = others[i].getBoundingClientRect();
      if (y < box.top + box.height / 2) { before = others[i]; break; }
    }
    if (before) {
      if (drag.row.nextElementSibling !== before) body.insertBefore(drag.row, before);
    } else if (others.length && body.lastElementChild !== drag.row) {
      body.appendChild(drag.row);
    }
    // scroll the page when dragging near the top/bottom edge
    if (y < 70) window.scrollBy(0, -14);
    else if (y > window.innerHeight - 70) window.scrollBy(0, 14);
  });

  function endDrag(event) {
    if (!drag || event.pointerId !== drag.pointerId) return;
    drag.row.classList.remove('is-dragging');
    drag = null;
    save();
  }

  body.addEventListener('pointerup', endDrag);
  body.addEventListener('pointercancel', endDrag);

  // ---- keyboard / button alternatives
  function move(row, direction) {
    var sibling = direction < 0 ? row.previousElementSibling : row.nextElementSibling;
    if (!sibling || !sibling.hasAttribute('data-reorder-id')) return false;
    if (direction < 0) body.insertBefore(row, sibling);
    else body.insertBefore(sibling, row);
    return true;
  }

  body.addEventListener('click', function (event) {
    var button = event.target.closest('[data-move]');
    if (!button) return;
    var row = button.closest('tr');
    if (move(row, button.getAttribute('data-move') === 'up' ? -1 : 1)) {
      button.focus();
      saveSoon();
    }
  });

  body.addEventListener('keydown', function (event) {
    var handle = event.target.closest('[data-reorder-handle]');
    if (!handle || (event.key !== 'ArrowUp' && event.key !== 'ArrowDown')) return;
    event.preventDefault();
    if (move(handle.closest('tr'), event.key === 'ArrowUp' ? -1 : 1)) {
      handle.focus();
      saveSoon();
    }
  });
})();
