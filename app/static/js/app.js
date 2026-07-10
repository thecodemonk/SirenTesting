/* ARPSC Manager client-side JS */

document.addEventListener('DOMContentLoaded', function () {
  // Text filter for siren table
  var filterInput = document.getElementById('siren-filter');
  var table = document.getElementById('siren-table');
  if (filterInput && table) {
    filterInput.addEventListener('input', function () {
      var query = this.value.toLowerCase();
      var rows = table.querySelectorAll('tbody tr');
      rows.forEach(function (row) {
        var text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
      });
    });
  }

  // Status filter buttons. "needs-testing" is a virtual filter that combines
  // overdue/flagged/untested rows, with an optional "Only Overdue" sub-filter.
  var statusFilter = document.getElementById('status-filter');
  var onlyOverdueWrapper = document.getElementById('only-overdue-wrapper');
  var onlyOverdueCheckbox = document.getElementById('only-overdue');
  if (statusFilter && table) {
    var initialActive = statusFilter.querySelector('.btn.active');
    var currentStatus = initialActive ? initialActive.dataset.status : 'all';
    var needsTestingSet = ['overdue', 'flagged', 'untested'];

    function applyFilter() {
      var onlyOverdue = onlyOverdueCheckbox && onlyOverdueCheckbox.checked;
      var rows = table.querySelectorAll('tbody tr');
      rows.forEach(function (row) {
        var rs = row.dataset.status;
        var show;
        if (currentStatus === 'all') {
          show = true;
        } else if (currentStatus === 'needs-testing') {
          show = onlyOverdue ? rs === 'overdue' : needsTestingSet.indexOf(rs) !== -1;
        } else {
          show = rs === currentStatus;
        }
        row.style.display = show ? '' : 'none';
      });
      if (onlyOverdueWrapper) {
        onlyOverdueWrapper.classList.toggle('d-none', currentStatus !== 'needs-testing');
      }
    }

    statusFilter.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-status]');
      if (!btn) return;
      statusFilter.querySelectorAll('.btn').forEach(function (b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
      currentStatus = btn.dataset.status;
      applyFilter();
    });

    if (onlyOverdueCheckbox) {
      onlyOverdueCheckbox.addEventListener('change', applyFilter);
    }

    applyFilter();
  }

  // Conditional rotation field on test form
  var sirenSelect = document.querySelector('select[name="siren_id"]');
  var rotationField = document.getElementById('rotation-field');
  if (sirenSelect && rotationField) {
    function toggleRotation() {
      var selected = sirenSelect.options[sirenSelect.selectedIndex];
      var sirenType = selected ? selected.dataset.type : '';
      rotationField.style.display = sirenType === 'ROTATE' ? '' : 'none';
    }
    sirenSelect.addEventListener('change', toggleRotation);
    toggleRotation();
  }

  // Confirm dialogs for destructive actions. Listen for `submit` on forms
  // and `click` on buttons/links — without this, putting data-confirm on a
  // <form> silently does nothing because the click event fires on the button.
  document.querySelectorAll('form[data-confirm]').forEach(function (el) {
    el.addEventListener('submit', function (e) {
      if (!confirm(el.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });
  document.querySelectorAll('button[data-confirm], a[data-confirm]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      if (!confirm(el.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });

  // Row click navigation for siren table
  if (table) {
    table.querySelectorAll('tbody tr').forEach(function (row) {
      row.addEventListener('click', function (e) {
        if (e.target.tagName === 'A') return;
        var link = row.querySelector('a');
        if (link) window.location = link.href;
      });
    });
  }

  // Generic clickable rows with keyboard support. Use class js-clickable-row
  // and a data-href attribute. Rows must also be tabindex=0 role=link so
  // screen readers and keyboard users can reach and activate them.
  document.querySelectorAll('.js-clickable-row').forEach(function (row) {
    var href = row.dataset.href;
    if (!href) return;
    row.addEventListener('click', function (e) {
      // Don't intercept clicks on inner links/buttons/forms
      if (e.target.closest('a, button, input, label, form')) return;
      window.location = href;
    });
    row.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        if (e.target.closest('a, button, input, label, form')) return;
        e.preventDefault();
        window.location = href;
      }
    });
  });

  // Format any <time class="js-localtime" datetime="<ISO>"> into the visitor's
  // own locale and time zone. The server emits raw ISO 8601 (with offset); the
  // browser is the only place that knows the user's actual time zone.
  document.querySelectorAll('.js-localtime').forEach(function (el) {
    var iso = el.getAttribute('datetime');
    if (!iso) return;
    var d = new Date(iso);
    if (isNaN(d.getTime())) return; // leave the original text if unparseable
    el.textContent = d.toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit', timeZoneName: 'short'
    });
  });

  // Training form: show/hide custom type field
  var trainingTypeSelect = document.getElementById('training-type-select');
  var customTypeGroup = document.getElementById('custom-type-group');
  if (trainingTypeSelect && customTypeGroup) {
    function toggleCustomType() {
      customTypeGroup.style.display = trainingTypeSelect.value === 'Other' ? '' : 'none';
    }
    trainingTypeSelect.addEventListener('change', toggleCustomType);
    toggleCustomType();
  }
});
