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

  // Status filter buttons
  var statusFilter = document.getElementById('status-filter');
  if (statusFilter && table) {
    statusFilter.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-status]');
      if (!btn) return;
      // Update active state
      statusFilter.querySelectorAll('.btn').forEach(function (b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
      var status = btn.dataset.status;
      var rows = table.querySelectorAll('tbody tr');
      rows.forEach(function (row) {
        if (status === 'all' || row.dataset.status === status) {
          row.style.display = '';
        } else {
          row.style.display = 'none';
        }
      });
    });
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
