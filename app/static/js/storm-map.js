/* Storm Center maps — Leaflet + OpenStreetMap.
   Uses circleMarker / divIcon so no marker-image assets are needed. */

var STORM_DEFAULT_CENTER = [42.97, -82.42]; // St. Clair County, MI
var OSM_TILES = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
var OSM_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function initStormMap(elId, data) {
  var el = document.getElementById(elId);
  if (!el || typeof L === 'undefined') return;
  var map = L.map(elId);
  L.tileLayer(OSM_TILES, { maxZoom: 19, attribution: OSM_ATTR }).addTo(map);
  var group = L.featureGroup().addTo(map);

  if (data.alerts && data.alerts.features && data.alerts.features.length) {
    L.geoJSON(data.alerts, {
      style: { color: '#dc3545', weight: 2, fillOpacity: 0.10 },
      onEachFeature: function (f, layer) {
        if (f.properties && f.properties.event) {
          layer.bindPopup('<strong>' + f.properties.event + '</strong>');
        }
      }
    }).addTo(group);
  }

  (data.points || []).forEach(function (p) {
    var m = L.circleMarker([p.lat, p.lng], {
      radius: 8, color: '#b02a37', fillColor: '#dc3545', fillOpacity: 0.9, weight: 2
    });
    var html = '<strong>' + p.type + '</strong>';
    if (p.thumb) html += '<br><img src="' + p.thumb + '" style="max-width:160px;margin-top:4px">';
    if (p.desc) html += '<br>' + p.desc;
    if (p.url) html += '<br><a href="' + p.url + '">Details</a>';
    m.bindPopup(html);
    m.addTo(group);
  });

  var bounds = group.getBounds();
  if (bounds.isValid()) {
    map.fitBounds(bounds.pad(0.2));
  } else {
    map.setView(data.center || STORM_DEFAULT_CENTER, 9);
  }
}

/* Location picker for the damage-report form. Click or drag to set a pin;
   writes "lat,lng" into the hidden field. Exposes window.stormSetPoint so the
   "Use my location" button can drop the pin too. */
function initDamagePicker(elId, fieldId, statusId) {
  var el = document.getElementById(elId);
  var field = document.getElementById(fieldId);
  if (!el || !field || typeof L === 'undefined') return;

  var statusEl = statusId ? document.getElementById(statusId) : null;
  var pinIcon = L.divIcon({
    className: 'damage-pin', html: '📍',
    iconSize: [28, 28], iconAnchor: [14, 26]
  });
  var map = L.map(elId).setView(STORM_DEFAULT_CENTER, 10);
  L.tileLayer(OSM_TILES, { maxZoom: 19, attribution: OSM_ATTR }).addTo(map);
  var marker = null;

  function place(lat, lng, recenter) {
    lat = parseFloat(lat); lng = parseFloat(lng);
    if (isNaN(lat) || isNaN(lng)) return;
    var val = lat.toFixed(5) + ',' + lng.toFixed(5);
    if (marker) {
      marker.setLatLng([lat, lng]);
    } else {
      marker = L.marker([lat, lng], { draggable: true, icon: pinIcon }).addTo(map);
      marker.on('dragend', function (e) {
        var ll = e.target.getLatLng();
        field.value = ll.lat.toFixed(5) + ',' + ll.lng.toFixed(5);
        if (statusEl) statusEl.textContent = 'Location set: ' + field.value;
      });
    }
    field.value = val;
    if (statusEl) statusEl.textContent = 'Location set: ' + val;
    if (recenter) map.setView([lat, lng], 14);
  }

  map.on('click', function (e) { place(e.latlng.lat, e.latlng.lng); });
  window.stormSetPoint = place;

  if (field.value) {
    var parts = field.value.split(',');
    place(parts[0], parts[1], true);
  }
}
