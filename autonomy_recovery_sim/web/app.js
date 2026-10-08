const canvas = document.querySelector("#scene");
const context = canvas.getContext("2d");
const keys = new Set();
let state = null;
let sendingControl = false;
let pollPromise = null;
let pendingCommands = 0;
let stateGeneration = 0;
let runCommandInFlight = false;
let connectionFailed = false;
const runToggleGuardMs = 450;
let lastRunIntent = null;
let lastRunIntentAt = 0;
const perceptionGeometryCache = { key: null, visiblePolygons: [] };
const egoMinibusModel = { asset: null, error: null };
const mapCamera = { zoom: 8, panX: 0, panY: 0, followEgo: true };
const perspectiveCamera = { yawOffset: 0, pitch: .19, zoom: 1 };
const mapPointers = new Map();
const perspectivePointers = new Map();
let panOrigin = null;
let pinchOrigin = null;
let perspectiveOrigin = null;
let perspectivePinchOrigin = null;
let viewMode = "perspective";
let perceptionVisible = true;
try {
  viewMode = localStorage.getItem("autonomy-recovery-sim-view") || "perspective";
  const storedPerception = localStorage.getItem("autonomy-recovery-sim-perception");
  perceptionVisible = storedPerception !== "hidden";
} catch (_) {
  viewMode = "perspective";
}
const requestedView = new URLSearchParams(window.location.search).get("view");
if (["perspective", "topdown"].includes(requestedView)) viewMode = requestedView;

const commandLabels = {
  WAIT: "Warten",
  REPLAN_ROUTE: "Route neu planen",
  REVERSE_SHORT: "Kurz zurücksetzen",
  PULL_OVER: "An den Rand fahren",
  NUDGE_AROUND_OBSTACLE: "Hindernis umfahren",
  CHANGE_LANE: "Spur wechseln",
  AVOID_TEMPORARY_OBSTRUCTION: "Vorübergehendes Hindernis umfahren",
  CROSS_LOW_RISK_OBJECT: "Niedrigrisiko-Objekt langsam überrollen",
  REQUEST_REMOTE_ASSISTANCE: "Remote Assistance anfordern",
  ABORT_MISSION: "Mission abbrechen",
  SAFE_STOP: "Sicherer Halt",
  RETURN_HOME: "Zurück zum Hub",
  DROP_PASSENGER: "Fahrgäste absetzen",
  REQUEST_ADDITIONAL_INFORMATION: "Weitere Informationen sammeln",
  ESCALATE_TO_RULE_ENGINE: "An Regel-Engine übergeben",
};

const terminalTitles = {
  rerouted: "Alternativroute übernommen",
  safe_stopped: "Sicherer Halt erreicht",
  mission_aborted: "Mission abgebrochen",
  returned_home: "Rückfahrt zum Hub",
  passenger_dropped: "Fahrgäste abgesetzt",
};

const labels = {
  recovery_requested: "Stillstandsmonitor hat Autonomy Recovery angefordert",
  command_started: "Befehl vom Ausführer übernommen",
  command_finished: "Befehl abgeschlossen",
  command_budget_exhausted: "Befehlsbudget der Episode erschöpft",
  remote_assistance_requested: "Remote Assistance angefordert",
  remote_assistance_cleared: "Leitstelle hat die Blockade aufgelöst",
  passengers_dropped: "Fahrgäste ausgestiegen",
  episode_terminated: "Episode beendet",
  pull_over_released: "Rand verlassen, Weiterfahrt",
  liberated: "Blockade erfolgreich passiert",
  collision: "Kollision erkannt",
  goal_reached: "Zielposition erreicht",
  mode_changed: "Fahrmodus geändert",
  contract_expired: "Manöverfreigabe ist abgelaufen",
  agent_observation: "Situation für den Recovery Agent erfasst",
  agent_requested: "Deadlock erkannt · Entscheidungsagent benötigt",
  agent_activated: "Entscheidungsagent am Deadlock aktiviert",
  agent_decision: "Recovery Decision validiert",
  agent_contract_error: "Ungültige Agentenantwort abgefangen",
  maneuver_aborted: "Manöverfreigabe dynamisch widerrufen",
  abort_stabilized: "Ego sicher auf der eigenen Fahrbahn gestoppt",
  minimum_risk_completion: "Commit Point passiert · kontrollierter Abschluss",
};

const abortReasons = {
  oncoming_traffic: "Gegenverkehr ist in den Sicherheitshorizont eingetreten.",
  blocker_moves: "Das zuvor stehende Hindernis fährt wieder an.",
  collision_risk: "Im Fahrkorridor wurde ein neues Kollisionsrisiko erkannt.",
  contract_expired: "Die zeitliche oder räumliche Freigabegrenze wurde erreicht.",
};

const perceptionStyles = {
  visible: { color: "#087f73", alpha: 1, dash: [], label: "sichtbar" },
  partially_visible: { color: "#db6b2c", alpha: .7, dash: [5, 3], label: "teilweise sichtbar" },
  tracked: { color: "#6e5aa8", alpha: .36, dash: [5, 4], label: "Track" },
  occluded: { color: "#5d6662", alpha: .18, dash: [3, 4], label: "verdeckt" },
  outside_fov: { color: "#5d6662", alpha: .18, dash: [3, 4], label: "außerhalb Sichtfeld" },
  out_of_range: { color: "#5d6662", alpha: .18, dash: [3, 4], label: "außer Reichweite" },
  unknown: { color: "#5d6662", alpha: .5, dash: [3, 4], label: "unbekannt" },
};

function perceptionStyle(actor) {
  return perceptionStyles[actor.perception_status] || perceptionStyles.unknown;
}

function actorLabel(actor) {
  // Auch ein stehender Radfahrer bleibt Radverkehr: "Blockade" verschleiert
  // genau den ungeschuetzten Verkehrsteilnehmer, um den es im Szenario geht.
  const base = actor.kind === "bicycle" ? "Radverkehr"
    : actor.kind === "pedestrian" ? "Fußverkehr"
    : actor.kind === "animal" ? "Tier"
    : actor.kind === "train" ? "Güterzug"
    : actor.kind === "barrier" ? "Absperrung"
    : actor.speed_mps < .25 ? "Blockade" : "Gegenverkehr";
  if (!perceptionVisible) return base;
  const style = perceptionStyle(actor);
  const age = actor.perception_status === "tracked" && actor.track_age_s != null
    ? ` · ${Number(actor.track_age_s).toFixed(1).replace(".", ",")} s`
    : "";
  const truth = ["occluded", "outside_fov", "out_of_range"].includes(actor.perception_status)
    ? " · Ground Truth"
    : "";
  return `${base} · ${style.label}${age}${truth}`;
}

// ---- Verkehrssteuerung: Ampeln und Bahnuebergaenge -------------------------------------

const controlPalette = {
  RED: "#d33a2c", YELLOW: "#e0a63d", GREEN: "#2e9e5b", DARK: "#3a3f3d", OPEN: "#2e9e5b", CLOSED: "#d33a2c",
};
const controlLabels = {
  RED: "Ampel rot", YELLOW: "Ampel gelb", GREEN: "Ampel grün", DARK: "Ampel ausgefallen",
  OPEN: "Bahnübergang offen", CLOSED: "Schranke geschlossen",
};

function controlPoint(control, offset) {
  // Querablage in Routenkoordinaten: negativ = rechts der Strassenmitte
  return [control.x_m - Math.sin(control.yaw_rad) * offset, control.y_m + Math.cos(control.yaw_rad) * offset];
}

function drawTopControls(transform) {
  const lane = state.road.lane_width_m;
  (state.controls || []).forEach((control) => {
    const color = controlPalette[control.state] || "#3a3f3d";
    line([controlPoint(control, 0), controlPoint(control, -lane)], transform, 4, color);
    const [x, y] = transform(...controlPoint(control, -lane - 1.6));
    context.save();
    context.fillStyle = color;
    context.beginPath();
    context.arc(x, y, 7, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = "#17221f";
    context.font = "600 11px system-ui, sans-serif";
    context.fillText(controlLabels[control.state] || control.state, x + 12, y + 4);
    context.restore();
  });
}

function drawPerspectiveControls(project) {
  const lane = state.road.lane_width_m;
  (state.controls || []).forEach((control) => {
    const color = controlPalette[control.state] || "#3a3f3d";
    const stopA = controlPoint(control, 0);
    const stopB = controlPoint(control, -lane);
    const [foot0, foot1] = [project(stopA[0], stopA[1], 0), project(stopB[0], stopB[1], 0)];
    if (foot0 && foot1) {
      context.save();
      context.strokeStyle = color;
      context.lineWidth = 4;
      context.beginPath();
      context.moveTo(foot0.x, foot0.y);
      context.lineTo(foot1.x, foot1.y);
      context.stroke();
      context.restore();
    }
    const pole = controlPoint(control, -lane - 1.6);
    const base = project(pole[0], pole[1], 0);
    const top = project(pole[0], pole[1], 3.4);
    if (!base || !top || base.forward < -2 || base.forward > 160) return;
    const radius = Math.max(4, Math.min(16, 90 / Math.max(base.forward, 6)));
    context.save();
    context.strokeStyle = "#39413f";
    context.lineWidth = Math.max(2, radius / 3);
    context.beginPath();
    context.moveTo(base.x, base.y);
    context.lineTo(top.x, top.y);
    context.stroke();
    context.fillStyle = color;
    context.beginPath();
    context.arc(top.x, top.y, radius, 0, Math.PI * 2);
    context.fill();
    context.restore();
  });
}

function fitTransform(points, width, height, bounds = null) {
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const minX = bounds ? bounds[0][0] : Math.min(...xs) - 18;
  const maxX = bounds ? bounds[1][0] : Math.max(...xs) + 18;
  const minY = bounds ? bounds[0][1] : Math.min(...ys) - 14;
  const maxY = bounds ? bounds[1][1] : Math.max(...ys) + 14;
  const scale = Math.min(width / (maxX - minX), height / (maxY - minY));
  const offsetX = (width - (maxX - minX) * scale) / 2;
  const offsetY = (height - (maxY - minY) * scale) / 2;
  return (x, y) => [offsetX + (x - minX) * scale, height - offsetY - (y - minY) * scale];
}

function polygon(points, transform, fill, stroke = null) {
  if (!points.length) return;
  context.beginPath();
  points.forEach(([x, y], index) => {
    const [px, py] = transform(x, y);
    if (index === 0) context.moveTo(px, py);
    else context.lineTo(px, py);
  });
  context.closePath();
  context.fillStyle = fill;
  context.fill();
  if (stroke) {
    context.lineWidth = .7;
    context.strokeStyle = stroke;
    context.stroke();
  }
}

function polygonUnion(shapes, transform, fill, stroke = null) {
  // Alle Teilflaechen in einem Pfad: Die Nonzero-Regel fuellt Ueberlappungen
  // nur einmal, sonst wuerde sich die Transparenz der Sensorfaecher addieren.
  context.beginPath();
  shapes.forEach((points) => {
    if (!points.length) return;
    points.forEach(([x, y], index) => {
      const [px, py] = transform(x, y);
      if (index === 0) context.moveTo(px, py);
      else context.lineTo(px, py);
    });
    context.closePath();
  });
  context.fillStyle = fill;
  context.fill();
  if (stroke) {
    context.lineWidth = .7;
    context.strokeStyle = stroke;
    context.stroke();
  }
}

function line(points, transform, width, stroke, dash = []) {
  context.beginPath();
  points.forEach(([x, y], index) => {
    const [px, py] = transform(x, y);
    if (index === 0) context.moveTo(px, py);
    else context.lineTo(px, py);
  });
  context.lineWidth = width;
  context.strokeStyle = stroke;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.setLineDash(dash);
  context.stroke();
  context.setLineDash([]);
}

function drawTopVehicle(vehicle, transform, fill, label, stationary = false) {
  const [x, y] = transform(vehicle.x_m, vehicle.y_m);
  const [x2] = transform(vehicle.x_m + vehicle.length_m, vehicle.y_m);
  const scale = Math.abs(x2 - x) / vehicle.length_m;
  const length = vehicle.length_m * scale;
  const width = vehicle.width_m * scale;
  if (vehicle.kind === "minibus" && egoMinibusModel.asset) {
    context.save();
    context.translate(x, y);
    context.rotate(-vehicle.yaw_rad);
    context.fillStyle = "rgba(23, 34, 31, .22)";
    context.fillRect(-length / 2 + 2, -width / 2 + 3, length, width);
    context.restore();
    if (AutonomyRecoveryVehicleAssets.drawTopDown(context, egoMinibusModel.asset, vehicle, transform)) {
      if (label) {
        context.fillStyle = "#17221f";
        context.font = "700 11px system-ui";
        context.fillText(label, x + 9, y - 9);
      }
      return;
    }
  }
  context.save();
  context.translate(x, y);
  context.rotate(-vehicle.yaw_rad);
  context.fillStyle = "rgba(23, 34, 31, .24)";
  context.fillRect(-length / 2 + 2, -width / 2 + 3, length, width);
  context.beginPath();
  const nose = vehicle.kind === "minibus" ? .48 : .42;
  context.moveTo(length * nose, -width * .42);
  context.lineTo(length * .5, -width * .28);
  context.lineTo(length * .5, width * .28);
  context.lineTo(length * nose, width * .42);
  context.lineTo(-length * .47, width * .46);
  context.lineTo(-length * .5, width * .34);
  context.lineTo(-length * .5, -width * .34);
  context.lineTo(-length * .47, -width * .46);
  context.closePath();
  context.fillStyle = fill;
  context.fill();
  if (stationary) {
    context.lineWidth = Math.max(1.5, scale * .7);
    context.strokeStyle = "#d66b2c";
    context.stroke();
  }
  context.fillStyle = vehicle.kind === "minibus" ? "#e9e7dd" : "rgba(232, 235, 231, .82)";
  context.fillRect(length * .03, -width * .34, length * .29, width * .68);
  context.fillStyle = "rgba(45, 58, 55, .68)";
  context.fillRect(-length * .30, -width * .35, length * .24, width * .7);
  context.restore();
  if (label) {
    context.fillStyle = "#17221f";
    context.font = "700 11px system-ui";
    context.fillText(label, x + 9, y - 9);
  }
}

function areaColor(area) {
  if (area.kind === "zoo") return "#bfd5b5";
  if (["park", "grass", "meadow", "forest", "scrub", "village_green", "recreation_ground"].includes(area.kind)) return "#cfdac7";
  if (["playground", "sand"].includes(area.kind)) return "#e6d8b8";
  if (["industrial", "commercial", "railway", "construction"].includes(area.kind)) return "#ddd7cf";
  if (area.kind === "cemetery") return "#c6d2c3";
  return "#e2dfd6";
}

function roadStyle(kind) {
  if (["secondary", "tertiary"].includes(kind)) return { width: 7.2, color: "#fbfaf5" };
  if (["residential", "living_street", "pedestrian"].includes(kind)) return { width: 5.2, color: "#f8f7f1" };
  if (["service", "track"].includes(kind)) return { width: 3.1, color: "#f4f2eb" };
  return { width: 1.15, color: "#b8bdb3", dash: kind === "steps" ? [2, 2] : [] };
}

function drawRoadLabels(roads, transform) {
  const named = new Map();
  roads.forEach((road) => {
    if (!road.name || road.name === "Wilhelm-Busch-Straße" || road.points_xy.length < 2) return;
    const length = road.points_xy.slice(1).reduce((sum, point, index) => {
      const previous = road.points_xy[index];
      return sum + Math.hypot(point[0] - previous[0], point[1] - previous[1]);
    }, 0);
    if (!named.has(road.name) || length > named.get(road.name).length) named.set(road.name, { road, length });
  });
  context.font = "600 9px system-ui";
  context.textAlign = "center";
  context.textBaseline = "middle";
  [...named.values()].filter((item) => item.length > 42).forEach(({ road }) => {
    const points = road.points_xy;
    const middle = Math.floor(points.length / 2);
    const a = points[Math.max(0, middle - 1)];
    const b = points[Math.min(points.length - 1, middle + 1)];
    const [ax, ay] = transform(a[0], a[1]);
    const [bx, by] = transform(b[0], b[1]);
    let angle = Math.atan2(by - ay, bx - ax);
    if (angle > Math.PI / 2 || angle < -Math.PI / 2) angle += Math.PI;
    context.save();
    context.translate((ax + bx) / 2, (ay + by) / 2);
    context.rotate(angle);
    context.lineWidth = 3;
    context.strokeStyle = "rgba(242, 239, 230, .9)";
    context.strokeText(road.name, 0, 0);
    context.fillStyle = "#7a807a";
    context.fillText(road.name, 0, 0);
    context.restore();
  });
  context.textAlign = "start";
  context.textBaseline = "alphabetic";
}

function drawCityContext(map, transform, meter) {
  if (!map) return;
  map.areas.forEach((area) => polygon(area.points_xy, transform, areaColor(area)));
  map.buildings.forEach((building) => polygon(building.points_xy, transform, "#cbc5b9", "#b7b0a5"));
  map.railways.forEach((rail) => {
    line(rail.points_xy, transform, Math.max(2.2, meter * 1.5), "#8c8984");
    line(rail.points_xy, transform, 1, "#f4f0e8", [4, 4]);
  });
  map.roads.forEach((road) => {
    const style = roadStyle(road.kind);
    line(road.points_xy, transform, style.width, style.color, style.dash || []);
  });
  map.waterways.forEach((waterway) => line(waterway.points_xy, transform, 3.5, "#8fb9bf"));
  drawRoadLabels(map.roads, transform);
}

function samplePolyline(points, spacing = 3) {
  const samples = [points[0]];
  for (let index = 0; index < points.length - 1; index += 1) {
    const a = points[index];
    const b = points[index + 1];
    const distance = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const steps = Math.max(1, Math.ceil(distance / spacing));
    for (let step = 1; step <= steps; step += 1) {
      const fraction = step / steps;
      samples.push([a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction]);
    }
  }
  return samples;
}

function pointAtPolylineDistance(points, targetDistance) {
  let travelled = 0;
  for (let index = 0; index < points.length - 1; index += 1) {
    const a = points[index];
    const b = points[index + 1];
    const segment = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (travelled + segment >= targetDistance) {
      const fraction = segment > 0 ? (targetDistance - travelled) / segment : 0;
      return [a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction];
    }
    travelled += segment;
  }
  return points[points.length - 1];
}

function polylineWindow(points, startDistance, endDistance, spacing = 1.5) {
  const start = Math.max(0, startDistance);
  const end = Math.max(start, endDistance);
  const result = [];
  for (let distance = start; distance < end; distance += spacing) {
    result.push(pointAtPolylineDistance(points, distance));
  }
  result.push(pointAtPolylineDistance(points, end));
  return result;
}

function offsetPolyline(points, offset) {
  return points.map((point, index) => {
    const before = points[Math.max(0, index - 1)];
    const after = points[Math.min(points.length - 1, index + 1)];
    const heading = Math.atan2(after[1] - before[1], after[0] - before[0]);
    return [point[0] - Math.sin(heading) * offset, point[1] + Math.cos(heading) * offset];
  });
}

function screenPolygon(points, fill, stroke = null, width = 1) {
  if (points.some((point) => !point)) return;
  context.beginPath();
  points.forEach((point, index) => {
    if (index === 0) context.moveTo(point.x, point.y);
    else context.lineTo(point.x, point.y);
  });
  context.closePath();
  context.fillStyle = fill;
  context.fill();
  if (stroke) {
    context.lineWidth = width;
    context.strokeStyle = stroke;
    context.stroke();
  }
}

function perspectiveProjector(width, height) {
  const cameraYaw = state.ego.yaw_rad + perspectiveCamera.yawOffset;
  const cosYaw = Math.cos(cameraYaw);
  const sinYaw = Math.sin(cameraYaw);
  const pitch = perspectiveCamera.pitch;
  const cosPitch = Math.cos(pitch);
  const sinPitch = Math.sin(pitch);
  const cameraBack = 10;
  const cameraHeight = 8;
  const focal = Math.min(height * .78, width * .44) * perspectiveCamera.zoom;
  const centerY = height * .34;
  return (x, y, z = 0) => {
    const dx = x - state.ego.x_m;
    const dy = y - state.ego.y_m;
    const lateral = -sinYaw * dx + cosYaw * dy;
    const forward = cosYaw * dx + sinYaw * dy;
    const cameraForward = forward + cameraBack;
    const vertical = z - cameraHeight;
    const depth = cameraForward * cosPitch - vertical * sinPitch;
    if (depth < 1.5) return null;
    const cameraY = cameraForward * sinPitch + vertical * cosPitch;
    return {
      // `lateral` is positive to the vehicle's left, while screen x grows right.
      x: width / 2 - lateral * focal / depth,
      y: centerY - cameraY * focal / depth,
      depth,
      forward,
      scale: focal / depth,
    };
  };
}

function perspectiveContinuousRibbon(points, widthM, project, fill, near = -10, far = 160) {
  const left = offsetPolyline(points, widthM / 2);
  const right = offsetPolyline(points, -widthM / 2);
  const leftProjected = [];
  const rightProjected = [];
  for (let index = 0; index < points.length; index += 1) {
    const center = project(points[index][0], points[index][1]);
    const leftPoint = project(left[index][0], left[index][1]);
    const rightPoint = project(right[index][0], right[index][1]);
    if (!center || !leftPoint || !rightPoint || center.forward < near || center.forward > far) continue;
    leftProjected.push(leftPoint);
    rightProjected.push(rightPoint);
  }
  if (leftProjected.length > 1) screenPolygon([...leftProjected, ...rightProjected.reverse()], fill);
}

function perspectiveRibbon(points, widthM, project, fill, near = -10, far = 160) {
  const segments = [];
  for (let index = 0; index < points.length - 1; index += 1) {
    const a = points[index];
    const b = points[index + 1];
    const heading = Math.atan2(b[1] - a[1], b[0] - a[0]);
    const nx = -Math.sin(heading) * widthM / 2;
    const ny = Math.cos(heading) * widthM / 2;
    const corners = [
      project(a[0] + nx, a[1] + ny),
      project(b[0] + nx, b[1] + ny),
      project(b[0] - nx, b[1] - ny),
      project(a[0] - nx, a[1] - ny),
    ];
    if (corners.some((point) => !point)) continue;
    const forward = corners.reduce((sum, point) => sum + point.forward, 0) / corners.length;
    if (forward >= near && forward <= far) segments.push({ corners, forward });
  }
  segments.sort((a, b) => b.forward - a.forward);
  segments.forEach((segment) => screenPolygon(segment.corners, fill));
}

function perspectiveStroke(points, widthM, project, stroke, dashEvery = 0) {
  for (let index = points.length - 2; index >= 0; index -= 1) {
    if (dashEvery && index % dashEvery >= Math.ceil(dashEvery / 2)) continue;
    const a = project(points[index][0], points[index][1], .025);
    const b = project(points[index + 1][0], points[index + 1][1], .025);
    if (!a || !b || (a.forward < -10 && b.forward < -10) || (a.forward > 170 && b.forward > 170)) continue;
    context.beginPath();
    context.moveTo(a.x, a.y);
    context.lineTo(b.x, b.y);
    context.lineCap = "round";
    context.lineWidth = Math.max(.65, widthM * (a.scale + b.scale) / 2);
    context.strokeStyle = stroke;
    context.stroke();
  }
}

function perspectiveSensorFan(points, origin, project, fill, closed) {
  const boundary = points.filter((point) => (
    Math.hypot(point[0] - origin.x, point[1] - origin.y) > .01
  ));
  const center = project(origin.x, origin.y, .03);
  if (!center || boundary.length < 2) return;
  const segmentCount = closed ? boundary.length : boundary.length - 1;
  for (let index = segmentCount - 1; index >= 0; index -= 1) {
    const a = project(boundary[index][0], boundary[index][1], .03);
    const next = (index + 1) % boundary.length;
    const b = project(boundary[next][0], boundary[next][1], .03);
    if (!a || !b || (a.forward < -10 && b.forward < -10)) continue;
    screenPolygon([center, a, b], fill);
  }
}

function perspectiveRoadWidth(kind) {
  if (["secondary", "tertiary"].includes(kind)) return 9;
  if (["residential", "living_street", "pedestrian"].includes(kind)) return 6;
  if (["service", "track"].includes(kind)) return 3.5;
  return .8;
}

function buildingFootprint(points) {
  if (points.length < 2) return points;
  const first = points[0];
  const last = points[points.length - 1];
  return first[0] === last[0] && first[1] === last[1] ? points.slice(0, -1) : points;
}

function buildingWallColor(a, b) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const length = Math.max(.001, Math.hypot(dx, dy));
  const light = (-dy * -.55 + dx * .83) / length;
  if (light > .35) return "#c5c0b6";
  if (light < -.35) return "#9f9b93";
  return "#b2ada4";
}

function drawPerspectiveBuilding(building, project) {
  const footprint = buildingFootprint(building.points_xy);
  const height = Number(building.height_m) || 0;
  const minHeight = Math.min(Number(building.min_height_m) || 0, height);
  if (footprint.length < 3 || height <= minHeight) return;

  const base = footprint.map((point) => project(point[0], point[1], minHeight));
  const roof = footprint.map((point) => project(point[0], point[1], height));
  if ([...base, ...roof].some((point) => !point)) return;

  const walls = footprint.map((point, index) => {
    const next = (index + 1) % footprint.length;
    const points = [base[index], base[next], roof[next], roof[index]];
    return {
      points,
      depth: points.reduce((sum, projected) => sum + projected.depth, 0) / points.length,
      fill: buildingWallColor(point, footprint[next]),
    };
  });
  walls.sort((a, b) => b.depth - a.depth);
  walls.forEach((wall) => screenPolygon(wall.points, wall.fill, "rgba(71, 73, 69, .24)", .55));
  screenPolygon(roof, "#d8d3c9", "rgba(71, 73, 69, .3)", .65);
}

function drawPerspectiveContext(project) {
  if (!state.context) return;
  state.context.areas.forEach((area) => {
    const projected = area.points_xy.map((point) => project(point[0], point[1], .01));
    if (projected.every(Boolean) && projected.some((point) => point.forward > -8 && point.forward < 150)) {
      screenPolygon(projected, areaColor(area));
    }
  });
  state.context.roads.forEach((road) => {
    perspectiveRibbon(road.points_xy, perspectiveRoadWidth(road.kind), project, "#ecebe6", -10, 155);
  });
  const visibleBuildings = state.context.buildings.map((building) => {
    const footprint = buildingFootprint(building.points_xy);
    const center = footprint.reduce(
      (sum, point) => [sum[0] + point[0] / footprint.length, sum[1] + point[1] / footprint.length],
      [0, 0],
    );
    return { building, anchor: project(center[0], center[1], 0) };
  }).filter((item) => item.anchor && item.anchor.forward > -8 && item.anchor.forward < 140);
  visibleBuildings.sort((a, b) => b.anchor.depth - a.anchor.depth);
  visibleBuildings.forEach((item) => drawPerspectiveBuilding(item.building, project));
}

function vehicleWorldCorners(vehicle, length, width, z) {
  const cosYaw = Math.cos(vehicle.yaw_rad);
  const sinYaw = Math.sin(vehicle.yaw_rad);
  return [[.5, .5], [.5, -.5], [-.5, -.5], [-.5, .5]].map(([along, across]) => ({
    x: vehicle.x_m + along * length * cosYaw - across * width * sinYaw,
    y: vehicle.y_m + along * length * sinYaw + across * width * cosYaw,
    z,
  }));
}

function vehicleHeight(kind) {
  if (kind === "minibus") return 1.95;
  if (kind === "bus") return 2.9;
  if (kind === "truck") return 2.7;
  if (kind === "bicycle") return 1.25;
  if (kind === "pedestrian") return 1.75;
  if (kind === "animal") return 1.4;
  if (kind === "train") return 3.6;
  if (kind === "barrier") return 1.1;
  return 1.45;
}

function drawPerspectiveVehicleLabel(vehicle, project, height, label) {
  if (!label) return;
  const anchor = project(vehicle.x_m, vehicle.y_m, height + .65);
  if (!anchor) return;
  context.font = "700 11px system-ui";
  context.textAlign = "center";
  context.fillStyle = "rgba(255, 253, 247, .94)";
  const textWidth = context.measureText(label).width;
  context.fillRect(anchor.x - textWidth / 2 - 5, anchor.y - 10, textWidth + 10, 16);
  context.fillStyle = "#17221f";
  context.fillText(label, anchor.x, anchor.y + 2);
  context.textAlign = "start";
}

function drawPerspectiveVehicle(vehicle, project, ego = false, label = "") {
  const height = vehicleHeight(vehicle.kind);
  const baseWorld = vehicleWorldCorners(vehicle, vehicle.length_m, vehicle.width_m, 0);
  const topWorld = vehicleWorldCorners(vehicle, vehicle.length_m * (vehicle.kind === "minibus" ? .94 : .82), vehicle.width_m * .88, height);
  const base = baseWorld.map((point) => project(point.x, point.y, point.z));
  const top = topWorld.map((point) => project(point.x, point.y, point.z));
  if ([...base, ...top].some((point) => !point)) return;
  if (ego && egoMinibusModel.asset) {
    screenPolygon(base, "rgba(23, 34, 31, .2)");
    if (AutonomyRecoveryVehicleAssets.drawPerspective(context, egoMinibusModel.asset, vehicle, project)) {
      drawPerspectiveVehicleLabel(vehicle, project, height, label);
      return;
    }
  }
  const side = ego ? "#076c63" : "#8c9190";
  const face = ego ? "#087f73" : "#9da2a1";
  const roof = ego && vehicle.kind === "minibus" ? "#ece9df" : "#b8bcba";
  const outline = !ego && vehicle.speed_mps < .25 ? "#d66b2c" : "rgba(50, 57, 55, .28)";
  const faces = [
    { points: [base[0], base[1], top[1], top[0]], fill: face },
    { points: [base[1], base[2], top[2], top[1]], fill: side },
    { points: [base[2], base[3], top[3], top[2]], fill: face },
    { points: [base[3], base[0], top[0], top[3]], fill: side },
  ].sort((a, b) => b.points.reduce((sum, point) => sum + point.depth, 0) - a.points.reduce((sum, point) => sum + point.depth, 0));
  faces.forEach((item) => screenPolygon(item.points, item.fill, outline, ego ? 1 : 1.2));
  screenPolygon(top, roof, outline, ego ? 1 : 1.2);

  const windowWorld = vehicleWorldCorners(vehicle, vehicle.length_m * .48, vehicle.width_m * .72, height + .02);
  const windows = windowWorld.map((point) => project(point.x, point.y, point.z));
  if (windows.every(Boolean)) screenPolygon(windows, "#445552");

  drawPerspectiveVehicleLabel(vehicle, project, height, label);
}

function drawScreenTag(text, x, y, color = "#17221f") {
  context.save();
  context.font = "750 10px system-ui";
  context.textAlign = "center";
  const width = context.measureText(text).width + 10;
  context.fillStyle = "rgba(255, 253, 247, .94)";
  context.fillRect(x - width / 2, y - 12, width, 17);
  context.fillStyle = color;
  context.fillText(text, x, y);
  context.restore();
}

function angleFromStart(angle, start) {
  const fullTurn = Math.PI * 2;
  return (angle - start + fullTurn) % fullTurn;
}

function sensorFootprint(origin, range, heading, fov, stepDegrees = 4) {
  const full = fov >= 359.5;
  const span = Math.PI * fov / 180;
  const start = heading - span / 2;
  const steps = Math.max(24, Math.ceil(fov / stepDegrees));
  const points = full ? [] : [[origin.x, origin.y]];
  for (let index = 0; index <= steps; index += 1) {
    const angle = start + span * index / steps;
    points.push([
      origin.x + Math.cos(angle) * range,
      origin.y + Math.sin(angle) * range,
    ]);
  }
  return points;
}

function raySegmentDistance(origin, angle, a, b) {
  const direction = [Math.cos(angle), Math.sin(angle)];
  const segment = [b[0] - a[0], b[1] - a[1]];
  const denominator = direction[0] * segment[1] - direction[1] * segment[0];
  if (Math.abs(denominator) < 1e-8) return null;
  const offset = [a[0] - origin.x, a[1] - origin.y];
  const rayDistance = (offset[0] * segment[1] - offset[1] * segment[0]) / denominator;
  const segmentPosition = (offset[0] * direction[1] - offset[1] * direction[0]) / denominator;
  if (rayDistance < 0 || segmentPosition < 0 || segmentPosition > 1) return null;
  return rayDistance;
}

function polygonNearOrigin(points, origin, range) {
  if (!points?.length) return false;
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  const dx = Math.max(Math.min(...xs) - origin.x, 0, origin.x - Math.max(...xs));
  const dy = Math.max(Math.min(...ys) - origin.y, 0, origin.y - Math.max(...ys));
  return Math.hypot(dx, dy) <= range + 8;
}

function perceptionOccluders(origin, range) {
  const buildings = (state.context?.buildings || []).filter((building) => {
    const height = Number(building.height_m) || 0;
    const minHeight = Number(building.min_height_m) || 0;
    return height > 1.4 && minHeight <= 1.4 && polygonNearOrigin(building.points_xy, origin, range);
  }).map((building) => buildingFootprint(building.points_xy));
  const vehicles = state.actors.filter((actor) => (
    Math.hypot(actor.x_m - origin.x, actor.y_m - origin.y) <= range + actor.length_m
  )).map((actor) => vehicleWorldCorners(actor, actor.length_m, actor.width_m, 0)
    .map((point) => [point.x, point.y]));
  return [...buildings, ...vehicles].filter((points) => points.length >= 3);
}

function sensorOrigins() {
  // Die Ecksensorik bestimmt, was das Ego wahrnimmt. Zeichnet das Overlay die
  // freie Sicht nur aus der Fahrzeugmitte, liegt ein Objekt im grauen Schatten
  // und traegt trotzdem das Etikett "teilweise sichtbar".
  const published = state.perception?.visibility?.sensor_origins_xy;
  if (!Array.isArray(published) || !published.length) {
    return [{ x: state.ego.x_m, y: state.ego.y_m }];
  }
  return published.map(([x, y]) => ({ x: Number(x), y: Number(y) }));
}

function visibleSensorPolygons(origins, range, heading, fov) {
  const cacheKey = [
    Math.floor((Number(state.time_s) || 0) * 2),
    origins.map((origin) => `${origin.x.toFixed(2)},${origin.y.toFixed(2)}`).join("|"),
    range.toFixed(1),
    fov.toFixed(1),
  ].join(":");
  if (perceptionGeometryCache.key === cacheKey) return perceptionGeometryCache.visiblePolygons;
  const polygons = origins.map((origin) => visibleSensorPolygon(origin, range, heading, fov));
  perceptionGeometryCache.key = cacheKey;
  perceptionGeometryCache.visiblePolygons = polygons;
  return polygons;
}

function visibleSensorPolygon(origin, range, heading, fov) {
  const full = fov >= 359.5;
  const span = Math.PI * fov / 180;
  const start = heading - span / 2;
  const occluders = perceptionOccluders(origin, range);
  const angles = [];
  const steps = Math.max(90, Math.ceil(fov / 2));
  for (let index = 0; index <= steps; index += 1) angles.push(start + span * index / steps);
  occluders.forEach((points) => points.forEach((point) => {
    const bearing = Math.atan2(point[1] - origin.y, point[0] - origin.x);
    const relative = angleFromStart(bearing, start);
    if (full || relative <= span + 1e-6) {
      angles.push(bearing - .0015, bearing, bearing + .0015);
    }
  }));
  angles.sort((a, b) => angleFromStart(a, start) - angleFromStart(b, start));

  const boundary = angles.map((angle) => {
    let distance = range;
    occluders.forEach((points) => {
      for (let index = 0; index < points.length; index += 1) {
        const hit = raySegmentDistance(origin, angle, points[index], points[(index + 1) % points.length]);
        if (hit != null && hit < distance) distance = hit;
      }
    });
    return [origin.x + Math.cos(angle) * distance, origin.y + Math.sin(angle) * distance];
  });
  return full ? boundary : [[origin.x, origin.y], ...boundary];
}

function drawTopDownPerception(transform) {
  if (!perceptionVisible || !state.perception?.visibility) return;
  const visibility = state.perception.visibility;
  const fov = Math.min(360, Number(visibility.horizontal_fov_deg) || 360);
  const range = Math.max(1, Number(visibility.effective_range_m || visibility.sensor_range_m) || 1);
  const origin = { x: state.ego.x_m, y: state.ego.y_m };
  const footprint = sensorFootprint(origin, range, state.ego.yaw_rad, fov);
  const visibleAreas = visibleSensorPolygons(sensorOrigins(), range, state.ego.yaw_rad, fov);
  polygon(footprint, transform, "rgba(23, 34, 31, .055)", "rgba(23, 34, 31, .16)");
  polygonUnion(visibleAreas, transform, "rgba(8, 127, 115, .14)", "rgba(8, 127, 115, .34)");

  const [centerX, centerY] = transform(state.ego.x_m, state.ego.y_m);
  for (let ring = 10; ring <= Math.min(range, 30); ring += 10) {
    const ringPoints = sensorFootprint(origin, ring, state.ego.yaw_rad, fov, 8)
      .filter((_, index) => fov >= 359.5 || index > 0);
    line(ringPoints, transform, 1, "rgba(8, 127, 115, .34)", [3, 5]);
  }
  context.beginPath();
  context.arc(centerX, centerY, 4, 0, Math.PI * 2);
  context.fillStyle = "#087f73";
  context.fill();
}

function drawTopActorPerception(actor, transform) {
  if (!perceptionVisible) return;
  const style = perceptionStyle(actor);
  const [x, y] = transform(actor.x_m, actor.y_m);
  const [x2] = transform(actor.x_m + actor.length_m, actor.y_m);
  const scale = Math.abs(x2 - x) / actor.length_m;
  context.save();
  context.translate(x, y);
  context.rotate(-actor.yaw_rad);
  context.setLineDash(style.dash);
  context.strokeStyle = style.color;
  context.lineWidth = 1.6;
  context.strokeRect(
    -actor.length_m * scale / 2 - 3,
    -actor.width_m * scale / 2 - 3,
    actor.length_m * scale + 6,
    actor.width_m * scale + 6,
  );
  context.restore();
  drawScreenTag(actorLabel(actor), x, y - actor.width_m * scale / 2 - 8, style.color);
}

function drawPerspectivePerception(project) {
  if (!perceptionVisible || !state.perception?.visibility) return;
  const visibility = state.perception.visibility;
  const fov = Math.min(360, Number(visibility.horizontal_fov_deg) || 360);
  const range = Math.max(1, Number(visibility.effective_range_m || visibility.sensor_range_m) || 1);
  const origin = { x: state.ego.x_m, y: state.ego.y_m };
  const closed = fov >= 359.5;
  const origins = sensorOrigins();
  const footprint = sensorFootprint(origin, range, state.ego.yaw_rad, fov);
  const visibleAreas = visibleSensorPolygons(origins, range, state.ego.yaw_rad, fov);
  perspectiveSensorFan(footprint, origin, project, "rgba(23, 34, 31, .035)", closed);
  // Ein Faecher je Sensorursprung: Der schmale Keil, der an einem Hindernis
  // vorbeireicht, ist genau der Grund, warum ein Objekt dahinter noch als
  // teilweise sichtbar gemeldet wird.
  visibleAreas.forEach((area, index) => {
    perspectiveSensorFan(area, origins[index], project, "rgba(8, 127, 115, .05)", closed);
  });
}

function drawPerspectiveActorPerception(actor, project) {
  if (!perceptionVisible) return;
  const style = perceptionStyle(actor);
  const height = vehicleHeight(actor.kind);
  const corners = vehicleWorldCorners(actor, actor.length_m * 1.06, actor.width_m * 1.12, height + .08)
    .map((point) => project(point.x, point.y, point.z));
  if (corners.some((point) => !point)) return;
  context.save();
  context.beginPath();
  corners.forEach((point, index) => index ? context.lineTo(point.x, point.y) : context.moveTo(point.x, point.y));
  context.closePath();
  context.setLineDash(style.dash);
  context.strokeStyle = style.color;
  context.lineWidth = 1.5;
  context.stroke();
  context.restore();
  const anchor = project(actor.x_m, actor.y_m, height + .65);
  if (anchor) drawScreenTag(actorLabel(actor), anchor.x, anchor.y, style.color);
}

function drawTopDown(width, height) {
  context.fillStyle = "#e8e6dd";
  context.fillRect(0, 0, width, height);
  const points = state.road.points_xy;
  const baseTransform = fitTransform(points, width, height, state.context?.bounds_xy || null);
  if (mapCamera.followEgo) {
    const [egoX, egoY] = baseTransform(state.ego.x_m, state.ego.y_m);
    mapCamera.panX = -(egoX - width / 2) * mapCamera.zoom;
    mapCamera.panY = -(egoY - height / 2) * mapCamera.zoom;
  }
  const transform = (x, y) => {
    const [baseX, baseY] = baseTransform(x, y);
    return [
      width / 2 + (baseX - width / 2) * mapCamera.zoom + mapCamera.panX,
      height / 2 + (baseY - height / 2) * mapCamera.zoom + mapCamera.panY,
    ];
  };
  const lane = state.road.lane_width_m;
  const [originX] = transform(0, 0);
  const [laneX] = transform(lane, 0);
  const meter = Math.abs(laneX - originX) / lane;
  drawCityContext(state.context, transform, meter);
  line(points, transform, lane * 2.55 * meter, "rgba(23, 34, 31, .16)");
  line(points, transform, lane * 2.25 * meter, "#46504f");
  line(points, transform, 1.2, "rgba(255,255,255,.72)", state.road.center_marking === "dashed" ? [8, 9] : []);
  drawTopControls(transform);
  drawTopDownPerception(transform);
  const trail = state.trajectory.map((point) => [point.x_m, point.y_m]);
  if (trail.length > 1) line(trail, transform, 2.5, "rgba(39, 203, 184, .8)");
  drawTopVlaPlan(transform, meter);
  state.actors.forEach((actor) => {
    const style = perceptionStyle(actor);
    context.save();
    context.globalAlpha = perceptionVisible ? style.alpha : 1;
    drawTopVehicle(actor, transform, "#9da3a1", perceptionVisible ? "" : actorLabel(actor), actor.speed_mps < .25);
    context.restore();
    drawTopActorPerception(actor, transform);
  });
  drawTopVehicle(state.ego, transform, "#087f73", "Ego-Kleinbus");
}

function drawPerspective(width, height) {
  context.fillStyle = "#e5e7e2";
  context.fillRect(0, 0, width, height * .25);
  context.fillStyle = "#d8dbd4";
  context.fillRect(0, height * .25, width, height * .75);
  const project = perspectiveProjector(width, height);
  drawPerspectiveContext(project);
  const road = samplePolyline(state.road.points_xy, 2.5);
  const laneWidth = state.road.lane_width_m;
  perspectiveContinuousRibbon(road, laneWidth * 2.22, project, "#555d5c", -10, 165);
  perspectiveStroke(offsetPolyline(road, -laneWidth), .12, project, "rgba(255,255,255,.8)");
  perspectiveStroke(offsetPolyline(road, laneWidth), .12, project, "rgba(255,255,255,.8)");
  perspectiveStroke(road, .09, project, "rgba(255,255,255,.72)", state.road.center_marking === "dashed" ? 6 : 0);

  const laneCenter = offsetPolyline(road, -laneWidth / 2);
  perspectiveContinuousRibbon(laneCenter, .48, project, state.mode === "autopilot" ? "rgba(34, 177, 162, .5)" : "rgba(255,255,255,.18)", -3, 90);
  drawPerspectivePerception(project);
  drawPerspectiveControls(project);
  drawPerspectiveVlaPlan(project);

  const actors = [...state.actors].sort((a, b) => {
    const pa = project(a.x_m, a.y_m);
    const pb = project(b.x_m, b.y_m);
    return (pb?.depth || 0) - (pa?.depth || 0);
  });
  actors.forEach((actor) => {
    const position = project(actor.x_m, actor.y_m);
    if (position && position.forward > -8 && position.forward < 150) {
      const style = perceptionStyle(actor);
      context.save();
      context.globalAlpha = perceptionVisible ? style.alpha : 1;
      drawPerspectiveVehicle(actor, project, false, perceptionVisible ? "" : actorLabel(actor));
      context.restore();
      drawPerspectiveActorPerception(actor, project);
    }
  });
  drawPerspectiveVehicle(state.ego, project, true, "Ego-Kleinbus");
}

// ---- VLA-Fahrstack (Mock): geplante 6,4-s-Trajektorie und Streuung --------------------

const vlaPlanColor = "rgba(110, 90, 168, .85)";

function vlaPlanPoints() {
  const plan = state?.vla;
  if (!plan?.trajectory_xy?.length || plan.trajectory?.stationary) return null;
  return [[state.ego.x_m, state.ego.y_m], ...plan.trajectory_xy];
}

function drawTopVlaPlan(transform, meter) {
  const points = vlaPlanPoints();
  if (!points) return;
  const spread = Number(state.vla.trajectory?.spread_m) || 0;
  line(points, transform, Math.max(3, spread * 2 * meter), "rgba(110, 90, 168, .16)");
  line(points, transform, 2, vlaPlanColor, [6, 5]);
}

function drawPerspectiveVlaPlan(project) {
  const points = vlaPlanPoints();
  if (!points) return;
  const spread = Number(state.vla.trajectory?.spread_m) || 0;
  perspectiveContinuousRibbon(points, Math.max(.4, spread * 2), project, "rgba(110, 90, 168, .14)", -3, 90);
  perspectiveStroke(points, .18, project, vlaPlanColor);
}

const vlaMetaLabels = {
  FOLLOW_LANE: "Spur folgen",
  FOLLOW_VEHICLE: "Folgefahrt",
  YIELD: "Vorrang gewähren",
  STOP: "Anhalten",
  NUDGE_LEFT: "Links vorbeitasten",
  NUDGE_RIGHT: "Rechts vorbeitasten",
  LANE_CHANGE_LEFT: "Spurwechsel links",
  LANE_CHANGE_RIGHT: "Spurwechsel rechts",
  CREEP: "Schrittfahrt",
  REVERSE: "Rückwärts",
  PULL_OVER: "Rechts ranfahren",
  MANUAL: "Manuell",
};

function renderVla() {
  const panel = document.querySelector("#vlaPanel");
  const vla = state?.vla;
  panel.hidden = !vla;
  if (!vla) return;
  document.querySelector("#vlaMeta").textContent = vlaMetaLabels[vla.meta_action] || vla.meta_action;
  const confidence = document.querySelector("#vlaConfidence");
  confidence.textContent = `Konfidenz ${Math.round(Number(vla.confidence) * 100)} %`;
  confidence.title = "Selbstauskunft des Modells, keine geprüfte Wahrscheinlichkeit";
  document.querySelector("#vlaReasoning").textContent = `„${vla.reasoning}“`;
  const plan = vla.trajectory || {};
  const parts = [
    plan.stationary ? "Plan: stehen bleiben" : `Plan: ${Number(plan.path_length_m || 0).toLocaleString("de-DE")} m in ${Number(plan.horizon_s || 6.4).toLocaleString("de-DE")} s`,
    `Streuung ${Number(plan.spread_m || 0).toLocaleString("de-DE")} m`,
    vla.instruction ? `Anweisung: ${vla.instruction}` : null,
    vla.perception_interface === "vla" ? "Lagewerkzeuge ohne Semantik" : null,
  ].filter(Boolean);
  document.querySelector("#vlaDetail").textContent = `${parts.join(" · ")}. Modellausgabe, kann falsch sein.`;
}

function draw() {
  const rect = canvas.getBoundingClientRect();
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const targetWidth = Math.round(rect.width * ratio);
  const targetHeight = Math.round(rect.height * ratio);
  if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
    canvas.width = targetWidth;
    canvas.height = targetHeight;
  }
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, rect.width, rect.height);
  context.fillStyle = "#e8e6dd";
  context.fillRect(0, 0, rect.width, rect.height);
  try {
    if (state) {
      if (viewMode === "topdown") drawTopDown(rect.width, rect.height);
      else drawPerspective(rect.width, rect.height);
    }
  } catch (error) {
    // Ein einzelner Zeichenfehler darf die Schleife nicht beenden, sonst
    // friert das Bild dauerhaft ein und jede Bedienung wirkt wirkungslos.
    console.error(error);
  } finally {
    requestAnimationFrame(draw);
  }
}

function formatEuro(value) {
  return `${Number(value || 0).toFixed(2).replace(".", ",")} €`;
}

function formatDecision() {
  const badge = document.querySelector("#decisionBadge");
  const title = document.querySelector("#decision");
  const reason = document.querySelector("#reason");
  if (state.collision) {
    title.textContent = "Kollision";
    badge.textContent = "Stopp";
    badge.className = "badge collision";
    reason.textContent = "Der Lauf wurde durch den Sicherheitsmonitor beendet.";
  } else if (state.console?.pending) {
    title.textContent = "Ihr Zug";
    badge.textContent = "Konsole";
    badge.className = "badge abort";
    reason.textContent = "Das Fahrzeug steht. Die Zeit ist angehalten, bis Sie in der Recovery Console einen Befehl senden.";
  } else if (state.agent?.status === "waiting_for_agent") {
    title.textContent = "Deadlock erkannt";
    badge.textContent = "Agent fehlt";
    badge.className = "badge abort";
    reason.textContent = "Das Fahrzeug wartet sicher. Für eine Entscheidung muss ein studentischer Agent angeschlossen werden.";
  } else if (state.agent?.status === "error") {
    title.textContent = "Agentenausgabe abgelehnt";
    badge.textContent = "Fehler";
    badge.className = "badge deny";
    reason.textContent = state.agent_error || "Die Agentenausgabe verletzt den Sicherheitsvertrag.";
  } else if (state.maneuver_aborted) {
    title.textContent = state.abort_stabilized ? "Manöver sicher abgebrochen" : "Abbruch wird stabilisiert";
    badge.textContent = state.abort_stabilized ? "gestoppt" : "Abbruch";
    badge.className = "badge abort";
    reason.textContent = abortReasons[state.abort_reason] || "Die Freigabe wurde aus Sicherheitsgründen widerrufen.";
  } else if (state.minimum_risk_completion) {
    title.textContent = "Kontrollierter Abschluss";
    badge.textContent = "Commit Point";
    badge.className = "badge abort";
    reason.textContent = "Ein Zurücklenken ist nicht mehr sicher; das begonnene Passieren wird kontrolliert beendet.";
  } else if (state.terminal_outcome) {
    title.textContent = terminalTitles[state.terminal_outcome] || state.terminal_outcome;
    badge.textContent = "beendet";
    badge.className = state.terminal_outcome === "rerouted" ? "badge release" : "badge abort";
    reason.textContent = `${state.command?.reason || ""} · Kosten ${formatEuro(state.costs?.total_eur)}`;
  } else if (state.active_command || state.command) {
    const active = state.active_command;
    const name = active || state.command.command;
    title.textContent = state.liberated ? "Blockade passiert" : `${commandLabels[name] || name}${active ? " läuft" : ""}`;
    badge.textContent = state.liberated ? "erledigt" : active ? "aktiv" : "Befehl";
    badge.className = "badge release";
    reason.textContent = `${state.command?.reason || ""} · Kosten ${formatEuro(state.costs?.total_eur)}`;
  } else {
    title.textContent = "Autonome Anfahrt";
    badge.textContent = "Autopilot";
    badge.className = "badge waiting";
    reason.textContent = "Der Entscheidungsagent bleibt bis zu einem erkannten Deadlock inaktiv.";
  }
}

function renderPerception() {
  const panel = document.querySelector("#perceptionPanel");
  const perception = state?.perception;
  if (!perception?.visibility) {
    document.querySelector("#perceptionState").textContent = "Keine Sensordaten";
    document.querySelector("#visibleRange").textContent = "–";
    document.querySelector("#detectedCount").textContent = "–";
    document.querySelector("#visibilityMeter").style.width = "0%";
    panel.classList.add("limited");
    return;
  }
  const visibility = perception.visibility;
  const available = Number(visibility.available_m) || 0;
  const required = Number(visibility.required_m) || 0;
  const ratio = required > 0 ? Math.min(1, available / required) : 0;
  const sufficient = Boolean(visibility.sufficient);
  panel.classList.toggle("limited", !sufficient);
  document.querySelector("#perceptionState").textContent = sufficient ? "Sichtkorridor frei" : "Sicht begrenzt";
  document.querySelector("#perceptionRate").textContent = `${Number(perception.update_rate_hz || 2).toLocaleString("de-DE")} Hz`;
  document.querySelector("#visibleRange").textContent = `${Math.round(available)} / ${Math.round(required)} m`;
  document.querySelector("#detectedCount").textContent = String(perception.detected_actor_ids?.length || 0);
  document.querySelector("#visibilityMeter").style.width = `${Math.max(2, ratio * 100)}%`;
  const fov = Math.round(Number(visibility.horizontal_fov_deg) || 0);
  const occludedAt = visibility.occluded_from_m;
  const prefix = occludedAt != null
    ? `Verdeckung ab ${Math.round(Number(occludedAt))} m.`
    : `Sichtfeld ${fov}° · Sensorreichweite ${Math.round(Number(visibility.sensor_range_m) || 0)} m.`;
  document.querySelector("#perceptionHint").textContent = `${prefix} Türkis = freie Sicht, Grau = theoretisches Sensorfeld. Durchscheinende Objekte = Ground Truth.`;
}

function renderReadout() {
  if (!state) return;
  document.querySelector("#speed").textContent = Math.round(state.ego.speed_mps * 3.6);
  document.querySelector("#time").textContent = `${state.time_s.toFixed(1).replace(".", ",")} s`;
  document.querySelector("#position").textContent = `${state.ego.s_m.toFixed(1).replace(".", ",")} m`;
  document.querySelector("#clearance").textContent = state.minimum_clearance_m == null ? "–" : `${state.minimum_clearance_m.toFixed(1).replace(".", ",")} m`;
  document.querySelector("#roadName").textContent = state.scenario.road_name;
  document.querySelector("#mapSource").href = state.scenario.source_url || "https://www.openstreetmap.org/copyright";
  document.querySelector("#scenarioId").textContent = `Szenario: ${state.scenario.id}`;

  const dot = document.querySelector("#runDot");
  const runLabel = document.querySelector("#runLabel");
  dot.className = `run-dot ${state.done ? "done" : state.paused ? "" : "live"}`;
  runLabel.textContent = state.done ? "Lauf beendet"
    : state.console?.pending ? "Wartet auf Ihren Befehl"
    : state.paused ? "Pausiert" : "Simulation läuft";
  renderRunControl();
  document.querySelector("#stepButton").disabled = state.done;

  const manual = state.mode === "manual";
  document.querySelector("#manualHelp").hidden = !manual;
  document.querySelector("#autoButton").classList.toggle("active", !manual);
  document.querySelector("#manualButton").classList.toggle("active", manual);
  document.querySelector("#autoButton").setAttribute("aria-pressed", String(!manual));
  document.querySelector("#manualButton").setAttribute("aria-pressed", String(manual));
  formatDecision();
  renderConsole();
  renderPerception();
  renderVla();

  const list = document.querySelector("#eventList");
  document.querySelector("#eventCount").textContent = state.events.length;
  if (!state.events.length) {
    list.innerHTML = '<li class="empty">Noch keine Ereignisse.</li>';
  } else {
    list.innerHTML = [...state.events].reverse().map((event) =>
      `<li><time>${event.time_s.toFixed(1).replace(".", ",")} s</time><span>${labels[event.event] || event.event}</span></li>`
    ).join("");
  }
}

// ---- Recovery Console: ein Mensch uebernimmt die Agentensitzung --------------------------

const consoleUi = { session: null, command: null, toolsKey: null };
const consoleEl = (id) => document.querySelector(`#${id}`);

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]
  ));
}

function consoleCatalog() {
  return state?.agent_observation?.available_commands || [];
}

function defaultParameterValue(spec) {
  if (spec.default !== undefined) return spec.default;
  if (spec.type === "number") {
    const low = spec.minimum ?? 0;
    const high = spec.maximum ?? low + 10;
    return Math.round((low + (high - low) * 0.4) * 2) / 2;
  }
  return "";
}

function buildParameterForm(entry) {
  const grid = consoleEl("consoleParams");
  const required = new Set(entry.required_parameters || []);
  grid.innerHTML = Object.entries(entry.parameter_schema || {}).map(([name, spec]) => {
    const label = `${name}${required.has(name) ? "" : " (optional)"}`;
    const value = defaultParameterValue(spec);
    if (spec.enum) {
      const options = spec.enum.map((item) => `<option value="${escapeHtml(item)}"${item === value ? " selected" : ""}>${escapeHtml(item)}</option>`).join("");
      return `<label class="field"><span>${escapeHtml(label)}</span><select data-param="${escapeHtml(name)}" data-kind="enum">${options}</select></label>`;
    }
    if (spec.type === "boolean") {
      return `<label class="field check"><input type="checkbox" data-param="${escapeHtml(name)}" data-kind="bool"${value === true ? " checked" : ""}><span>${escapeHtml(label)}</span></label>`;
    }
    if (spec.type === "number") {
      const bounds = `${spec.minimum !== undefined ? ` min="${spec.minimum}"` : ""}${spec.maximum !== undefined ? ` max="${spec.maximum}"` : ""}`;
      return `<label class="field"><span>${escapeHtml(label)}${spec.minimum !== undefined ? ` · ${spec.minimum}–${spec.maximum}` : ""}</span><input type="number" step="0.5"${bounds} value="${value}" data-param="${escapeHtml(name)}" data-kind="number"></label>`;
    }
    return `<label class="field"><span>${escapeHtml(label)}</span><input type="text" maxlength="${spec.maxLength || 200}" data-param="${escapeHtml(name)}" data-kind="string"></label>`;
  }).join("");
}

function collectCommandPayload() {
  const parameters = {};
  consoleEl("consoleParams").querySelectorAll("[data-param]").forEach((input) => {
    const { param, kind } = input.dataset;
    if (kind === "bool") parameters[param] = input.checked;
    else if (kind === "number") {
      // Leere oder ungueltige Zahlen gehen unveraendert an den Server, der sie ablehnt und begruendet.
      parameters[param] = input.value === "" ? null : Number(input.value);
    } else if (input.value !== "") parameters[param] = input.value;
  });
  return {
    command: consoleEl("consoleCommand").value,
    parameters,
    reason: consoleEl("consoleReason").value.trim() || "Manuelle Demonstration",
  };
}

function renderConsoleTools(consoleState) {
  const tools = state?.agent_observation?.available_tools || [];
  const key = `${consoleState.session}:${consoleState.called_tools.join(",")}`;
  if (consoleUi.toolsKey === key) return;
  consoleUi.toolsKey = key;
  const called = new Set(consoleState.called_tools);
  consoleEl("consoleTools").innerHTML = tools.map((tool) => {
    const done = called.has(tool.name);
    const result = consoleState.tool_results[tool.name];
    return `<li class="${done ? "done" : ""}">
      <button type="button" data-tool="${escapeHtml(tool.name)}" title="${escapeHtml(tool.description)}">${escapeHtml(tool.name)}</button>
      <span class="tick" aria-label="${done ? "abgefragt" : "offen"}">${done ? "✓" : ""}</span>
      ${done ? `<details><summary>Ergebnis</summary><pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre></details>` : ""}
    </li>`;
  }).join("");
}

function renderConsole() {
  const panel = consoleEl("recoveryConsole");
  const consoleState = state?.console;
  panel.hidden = !consoleState?.enabled;
  if (!consoleState?.enabled) return;

  const form = consoleEl("consoleForm");
  form.hidden = !consoleState.pending;
  consoleEl("consoleBudget").textContent = consoleState.pending
    ? `Werkzeuge ${consoleState.tool_calls}/${consoleState.max_tool_calls} · Versuche ${consoleState.decision_attempts}/${consoleState.max_decision_attempts}`
    : "";
  if (!consoleState.pending) {
    consoleUi.session = null;
    consoleUi.toolsKey = null;
    consoleEl("consoleTitle").textContent = state.active_command
      ? `Befehl läuft: ${commandLabels[state.active_command] || state.active_command}`
      : "Warte auf Deadlock";
    consoleEl("consoleHint").textContent = state.done
      ? "Der Lauf ist beendet. Mit „Zurücksetzen“ beginnt ein neuer."
      : "Ohne angeschlossenen Agenten entscheiden Sie: Sobald das Fahrzeug festsitzt, öffnet sich hier die Sitzung. "
        + "Ihre Befehle durchlaufen dieselbe Regel- und Sicherheitsprüfung wie die eines Agenten; der Lauf zählt als „manuell“.";
    return;
  }

  consoleEl("consoleTitle").textContent = `Sitzung ${consoleState.session}: Sie sind am Zug`;
  consoleEl("consoleHint").textContent = "Die Zeit steht still. Erfassen Sie die Lage und wählen Sie genau einen Befehl.";
  const catalog = consoleCatalog();
  if (consoleUi.session !== consoleState.session) {
    consoleUi.session = consoleState.session;
    consoleUi.toolsKey = null;
    consoleEl("consoleCommand").innerHTML = catalog.map((entry) =>
      `<option value="${escapeHtml(entry.command)}">${escapeHtml(commandLabels[entry.command] || entry.command)} · ${escapeHtml(entry.command)}</option>`
    ).join("");
    consoleUi.command = null;
  }
  renderConsoleTools(consoleState);

  const selected = consoleEl("consoleCommand").value;
  const entry = catalog.find((item) => item.command === selected);
  if (entry && consoleUi.command !== selected) {
    consoleUi.command = selected;
    buildParameterForm(entry);
  }
  if (entry) {
    consoleEl("consoleCommandInfo").textContent = `${entry.description} Kosten: ${entry.cost_note || "–"}.${entry.ends_episode ? " Beendet die Episode." : ""}`;
    const missing = (entry.required_tools || []).filter((name) => !consoleState.called_tools.includes(name));
    consoleEl("consoleEvidenceHint").textContent = missing.length
      ? `Evidenz fehlt (${missing.length} Werkzeuge). Erst „Lagewerkzeuge abfragen“ – oder trotzdem senden und die Ablehnung ansehen.`
      : "";
  }
  const error = consoleEl("consoleError");
  error.hidden = !consoleState.error;
  error.textContent = consoleState.error || "";
}

consoleEl("consoleEvidence").addEventListener("click", () => dispatchCommand({ action: "console_evidence" }));
consoleEl("consoleTools").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-tool]");
  if (button) dispatchCommand({ action: "console_tool", name: button.dataset.tool });
});
consoleEl("consoleCommand").addEventListener("change", () => {
  consoleUi.command = null;
  renderConsole();
});
consoleEl("consoleSubmit").addEventListener("click", () => {
  dispatchCommand({ action: "console_submit", payload: collectCommandPayload() });
});

function renderRunControl() {
  const runButton = document.querySelector("#runButton");
  if (!state) {
    runButton.textContent = runCommandInFlight
      ? "Verbinde & starte …"
      : connectionFailed ? "Erneut verbinden & starten" : "Verbinde …";
    runButton.classList.add("primary");
    runButton.classList.toggle("is-loading", !connectionFailed || runCommandInFlight);
    runButton.disabled = runCommandInFlight;
    runButton.setAttribute("aria-busy", String(!connectionFailed || runCommandInFlight));
    return;
  }
  runButton.textContent = runCommandInFlight
    ? state.paused || state.done ? "Startet …" : "Pausiert …"
    : state.done ? "Neu starten" : state.paused ? "Starten" : "Pausieren";
  runButton.classList.toggle("primary", state.paused || state.done);
  runButton.classList.toggle("is-loading", runCommandInFlight);
  runButton.disabled = runCommandInFlight;
  runButton.setAttribute("aria-busy", String(runCommandInFlight));
}

function setPerceptionVisible(visible) {
  perceptionVisible = visible;
  const button = document.querySelector("#perceptionToggle");
  button.classList.toggle("active", visible);
  button.setAttribute("aria-pressed", String(visible));
  button.title = visible ? "Wahrnehmungsdiagnose ausblenden" : "Wahrnehmungsdiagnose einblenden";
  document.querySelector("#perceptionPanel").hidden = !visible;
  document.querySelector(".legend").hidden = !visible;
  try {
    localStorage.setItem("autonomy-recovery-sim-perception", visible ? "visible" : "hidden");
  } catch (_) {
    // Die Diagnoseansicht funktioniert auch ohne persistenten Browserspeicher.
  }
}

async function command(payload) {
  const generation = ++stateGeneration;
  pendingCommands += 1;
  try {
    const response = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`Steuerbefehl fehlgeschlagen: ${response.status}`);
    const nextState = await response.json();
    connectionFailed = false;
    if (generation === stateGeneration) {
      state = nextState;
      renderReadout();
    }
    return nextState;
  } finally {
    pendingCommands -= 1;
  }
}

function dispatchCommand(payload) {
  return command(payload).catch((error) => {
    connectionFailed = true;
    document.querySelector("#runLabel").textContent = "Steuerung nicht erreichbar · Server prüfen";
    document.querySelector("#runDot").className = "run-dot done";
    console.error(error);
    return null;
  });
}

async function poll() {
  if (pollPromise) return pollPromise;
  if (pendingCommands > 0) return state;
  const generation = stateGeneration;
  pollPromise = (async () => {
    try {
      const response = await fetch("/api/state", { cache: "no-store" });
      if (!response.ok) throw new Error(`Status ${response.status}`);
      const nextState = await response.json();
      connectionFailed = false;
      if (generation === stateGeneration && pendingCommands === 0) {
        state = nextState;
        renderReadout();
      }
      return nextState;
    } catch (error) {
      connectionFailed = true;
      document.querySelector("#runLabel").textContent = "Verbindung unterbrochen · Server prüfen";
      renderRunControl();
      return null;
    }
  })();
  try {
    return await pollPromise;
  } finally {
    pollPromise = null;
  }
}

async function toggleSimulationRunState(requestedAction = null) {
  if (runCommandInFlight) return;
  // Before the first status response the button already promises "Start".
  // Sending that idempotent command directly avoids racing the initial poll.
  const action = requestedAction
    || (!state || state.done || state.paused ? "start" : "pause");
  // Direkt nach dem Start bewegt sich der Kleinbus noch kaum sichtbar. Wer
  // deshalb ein zweites Mal klickt oder schlicht doppelklickt, sendet sonst
  // sofort "pause": die Simulation steht wieder bei t ~ 0 und der Startknopf
  // wirkt wirkungslos. Ein umkehrender Klick innerhalb des Schutzfensters ist
  // praktisch immer ein Doppelklick und kein Pausenwunsch.
  const now = typeof performance !== "undefined" ? performance.now() : Date.now();
  if (!requestedAction && lastRunIntent && action !== lastRunIntent
    && now - lastRunIntentAt < runToggleGuardMs) return;
  lastRunIntent = action;
  lastRunIntentAt = now;
  runCommandInFlight = true;
  renderRunControl();
  let result = null;
  try {
    result = await dispatchCommand({ action });
  } finally {
    runCommandInFlight = false;
  }
  if (result) {
    state = result;
    renderReadout();
  } else {
    renderRunControl();
  }
}

function manualControl() {
  if (!state || state.mode !== "manual") return;
  const throttle = keys.has("KeyW") || keys.has("ArrowUp") ? 1 : 0;
  const brake = keys.has("KeyS") || keys.has("ArrowDown") ? 1 : 0;
  const left = keys.has("KeyA") || keys.has("ArrowLeft");
  const right = keys.has("KeyD") || keys.has("ArrowRight");
  const steering = (left ? 1 : 0) - (right ? 1 : 0);
  if (!sendingControl) {
    sendingControl = true;
    dispatchCommand({ action: "control", throttle, brake, steering }).finally(() => { sendingControl = false; });
  }
}

function setViewMode(mode) {
  viewMode = mode === "topdown" ? "topdown" : "perspective";
  const perspective = viewMode === "perspective";
  document.querySelector("#perspectiveView").classList.toggle("active", perspective);
  document.querySelector("#mapView").classList.toggle("active", !perspective);
  document.querySelector("#perspectiveView").setAttribute("aria-pressed", String(perspective));
  document.querySelector("#mapView").setAttribute("aria-pressed", String(!perspective));
  document.querySelector("#perspectiveTools").hidden = !perspective;
  document.querySelector("#mapTools").hidden = perspective;
  document.querySelector(".stage").classList.toggle("map-mode", !perspective);
  document.querySelector(".stage").classList.toggle("perspective-mode", perspective);
  canvas.setAttribute(
    "aria-label",
    perspective
      ? "Perspektivische Fahransicht der Wilhelm-Busch-Straße"
      : "Top-down-Karte der Wilhelm-Busch-Straße",
  );
  try {
    localStorage.setItem("autonomy-recovery-sim-view", viewMode);
  } catch (_) {
    // Die Ansicht funktioniert auch ohne persistenten Browserspeicher.
  }
}

function updateMapZoomLabel() {
  document.querySelector("#mapZoom").textContent = `${Math.round(mapCamera.zoom * 100)} %`;
}

function updateMapFollowButton() {
  const button = document.querySelector("#resetMap");
  button.classList.toggle("active", mapCamera.followEgo);
  button.setAttribute("aria-pressed", String(mapCamera.followEgo));
  button.setAttribute(
    "aria-label",
    mapCamera.followEgo ? "Ego-Fahrzeug wird zentriert" : "Ego-Fahrzeug wieder zentrieren",
  );
  button.title = mapCamera.followEgo ? "Ego-Fahrzeug wird verfolgt" : "Ego-Fahrzeug wieder zentrieren";
}

function setMapFollow(follow) {
  mapCamera.followEgo = follow;
  updateMapFollowButton();
}

function zoomMapAt(nextZoom, x, y) {
  const rect = canvas.getBoundingClientRect();
  const clamped = Math.min(20, Math.max(.65, nextZoom));
  const centerX = rect.width / 2;
  const centerY = rect.height / 2;
  const ratio = clamped / mapCamera.zoom;
  mapCamera.panX = x - centerX - (x - centerX - mapCamera.panX) * ratio;
  mapCamera.panY = y - centerY - (y - centerY - mapCamera.panY) * ratio;
  mapCamera.zoom = clamped;
  updateMapZoomLabel();
}

function zoomMapBy(factor) {
  const rect = canvas.getBoundingClientRect();
  zoomMapAt(mapCamera.zoom * factor, rect.width / 2, rect.height / 2);
}

function centerMapOnEgo() {
  setMapFollow(true);
}

function updatePerspectiveZoomLabel() {
  document.querySelector("#cameraZoom").textContent = `${Math.round(perspectiveCamera.zoom * 100)} %`;
}

function zoomPerspectiveBy(factor) {
  perspectiveCamera.zoom = Math.min(2.5, Math.max(.5, perspectiveCamera.zoom * factor));
  updatePerspectiveZoomLabel();
}

function resetPerspectiveCamera() {
  perspectiveCamera.yawOffset = 0;
  perspectiveCamera.pitch = .19;
  perspectiveCamera.zoom = 1;
  updatePerspectiveZoomLabel();
}

function wrapCameraAngle(angle) {
  return Math.atan2(Math.sin(angle), Math.cos(angle));
}

function pointerPosition(event) {
  const rect = canvas.getBoundingClientRect();
  return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}

function startRemainingPointer() {
  if (mapPointers.size !== 1) return;
  const point = [...mapPointers.values()][0];
  panOrigin = {
    x: point.x,
    y: point.y,
    panX: mapCamera.panX,
    panY: mapCamera.panY,
    engaged: !mapCamera.followEgo,
  };
  pinchOrigin = null;
}

function startRemainingPerspectivePointer() {
  if (perspectivePointers.size !== 1) return;
  const point = [...perspectivePointers.values()][0];
  perspectiveOrigin = {
    x: point.x,
    y: point.y,
    yawOffset: perspectiveCamera.yawOffset,
    pitch: perspectiveCamera.pitch,
  };
  perspectivePinchOrigin = null;
}

const runButton = document.querySelector("#runButton");
const earlyRunRequested = Boolean(window.__autonomyRecoverySimEarlyRunRequested);
if (window.__autonomyRecoverySimEarlyRunCapture) {
  document.removeEventListener("click", window.__autonomyRecoverySimEarlyRunCapture, true);
}
window.__autonomyRecoverySimEarlyRunRequested = false;
runButton.addEventListener("click", () => toggleSimulationRunState());
document.querySelector("#stepButton").addEventListener("click", () => dispatchCommand({ action: "step" }));
document.querySelector("#resetButton").addEventListener("click", () => {
  // Zuruecksetzen ist ein eigener Wunsch: danach darf sofort wieder gestartet
  // werden, ohne auf das Doppelklick-Schutzfenster zu warten.
  lastRunIntent = null;
  return dispatchCommand({ action: "reset" });
});
document.querySelector("#autoButton").addEventListener("click", () => dispatchCommand({ mode: "autopilot" }));
document.querySelector("#manualButton").addEventListener("click", () => dispatchCommand({ mode: "manual" }));
document.querySelector("#speedFactor").addEventListener("change", (event) => dispatchCommand({ speed_factor: Number(event.target.value) }));
document.querySelector("#perspectiveView").addEventListener("click", () => setViewMode("perspective"));
document.querySelector("#mapView").addEventListener("click", () => setViewMode("topdown"));
document.querySelector("#perceptionToggle").addEventListener("click", () => setPerceptionVisible(!perceptionVisible));
document.querySelector("#zoomIn").addEventListener("click", () => {
  setMapFollow(false);
  zoomMapBy(1.35);
});
document.querySelector("#zoomOut").addEventListener("click", () => {
  setMapFollow(false);
  zoomMapBy(1 / 1.35);
});
document.querySelector("#resetMap").addEventListener("click", centerMapOnEgo);
document.querySelector("#cameraZoomIn").addEventListener("click", () => zoomPerspectiveBy(1.2));
document.querySelector("#cameraZoomOut").addEventListener("click", () => zoomPerspectiveBy(1 / 1.2));
document.querySelector("#resetPerspective").addEventListener("click", resetPerspectiveCamera);
canvas.addEventListener("wheel", (event) => {
  event.preventDefault();
  if (viewMode === "topdown") {
    setMapFollow(false);
    const point = pointerPosition(event);
    zoomMapAt(mapCamera.zoom * Math.exp(-event.deltaY * .0014), point.x, point.y);
  } else {
    zoomPerspectiveBy(Math.exp(-event.deltaY * .0014));
  }
}, { passive: false });
canvas.addEventListener("dblclick", (event) => {
  if (viewMode !== "topdown") return;
  setMapFollow(false);
  const point = pointerPosition(event);
  zoomMapAt(mapCamera.zoom * 1.6, point.x, point.y);
});
canvas.addEventListener("pointerdown", (event) => {
  if (event.button > 0) return;
  canvas.setPointerCapture(event.pointerId);
  const point = pointerPosition(event);
  if (viewMode === "topdown") {
    mapPointers.set(event.pointerId, point);
    document.querySelector(".stage").classList.add("dragging");
    if (mapPointers.size === 1) startRemainingPointer();
    if (mapPointers.size === 2) {
      setMapFollow(false);
      const [first, second] = [...mapPointers.values()];
      pinchOrigin = {
        distance: Math.max(1, Math.hypot(second.x - first.x, second.y - first.y)),
        zoom: mapCamera.zoom,
        panX: mapCamera.panX,
        panY: mapCamera.panY,
        midX: (first.x + second.x) / 2,
        midY: (first.y + second.y) / 2,
      };
      panOrigin = null;
    }
  } else {
    perspectivePointers.set(event.pointerId, point);
    document.querySelector(".stage").classList.add("rotating");
    if (perspectivePointers.size === 1) startRemainingPerspectivePointer();
    if (perspectivePointers.size === 2) {
      const [first, second] = [...perspectivePointers.values()];
      perspectivePinchOrigin = {
        distance: Math.max(1, Math.hypot(second.x - first.x, second.y - first.y)),
        zoom: perspectiveCamera.zoom,
      };
      perspectiveOrigin = null;
    }
  }
});
canvas.addEventListener("pointermove", (event) => {
  const point = pointerPosition(event);
  if (mapPointers.has(event.pointerId) && viewMode === "topdown") {
    mapPointers.set(event.pointerId, point);
    if (mapPointers.size === 1 && panOrigin) {
      const current = [...mapPointers.values()][0];
      const distance = Math.hypot(current.x - panOrigin.x, current.y - panOrigin.y);
      if (!panOrigin.engaged && distance < 3) return;
      if (!panOrigin.engaged) {
        panOrigin.engaged = true;
        setMapFollow(false);
        panOrigin.x = current.x;
        panOrigin.y = current.y;
        panOrigin.panX = mapCamera.panX;
        panOrigin.panY = mapCamera.panY;
      }
      mapCamera.panX = panOrigin.panX + current.x - panOrigin.x;
      mapCamera.panY = panOrigin.panY + current.y - panOrigin.y;
    } else if (mapPointers.size === 2 && pinchOrigin) {
      const rect = canvas.getBoundingClientRect();
      const [first, second] = [...mapPointers.values()];
      const distance = Math.max(1, Math.hypot(second.x - first.x, second.y - first.y));
      const midX = (first.x + second.x) / 2;
      const midY = (first.y + second.y) / 2;
      const nextZoom = Math.min(20, Math.max(.65, pinchOrigin.zoom * distance / pinchOrigin.distance));
      const ratio = nextZoom / pinchOrigin.zoom;
      mapCamera.zoom = nextZoom;
      mapCamera.panX = midX - rect.width / 2 - (pinchOrigin.midX - rect.width / 2 - pinchOrigin.panX) * ratio;
      mapCamera.panY = midY - rect.height / 2 - (pinchOrigin.midY - rect.height / 2 - pinchOrigin.panY) * ratio;
      updateMapZoomLabel();
    }
  } else if (perspectivePointers.has(event.pointerId) && viewMode === "perspective") {
    perspectivePointers.set(event.pointerId, point);
    if (perspectivePointers.size === 1 && perspectiveOrigin) {
      const current = [...perspectivePointers.values()][0];
      perspectiveCamera.yawOffset = wrapCameraAngle(
        perspectiveOrigin.yawOffset - (current.x - perspectiveOrigin.x) * .006,
      );
      perspectiveCamera.pitch = Math.min(.72, Math.max(.04, perspectiveOrigin.pitch + (current.y - perspectiveOrigin.y) * .004));
    } else if (perspectivePointers.size === 2 && perspectivePinchOrigin) {
      const [first, second] = [...perspectivePointers.values()];
      const distance = Math.max(1, Math.hypot(second.x - first.x, second.y - first.y));
      perspectiveCamera.zoom = Math.min(2.5, Math.max(.5, perspectivePinchOrigin.zoom * distance / perspectivePinchOrigin.distance));
      updatePerspectiveZoomLabel();
    }
  }
});
function endCanvasPointer(event) {
  if (mapPointers.delete(event.pointerId)) {
    if (!mapPointers.size) {
      panOrigin = null;
      pinchOrigin = null;
      document.querySelector(".stage").classList.remove("dragging");
    } else {
      startRemainingPointer();
    }
  }
  if (perspectivePointers.delete(event.pointerId)) {
    if (!perspectivePointers.size) {
      perspectiveOrigin = null;
      perspectivePinchOrigin = null;
      document.querySelector(".stage").classList.remove("rotating");
    } else {
      startRemainingPerspectivePointer();
    }
  }
}
canvas.addEventListener("pointerup", endCanvasPointer);
canvas.addEventListener("pointercancel", endCanvasPointer);
function isTypingTarget(event) {
  return Boolean(event.target?.closest?.("input, select, textarea"));
}

window.addEventListener("keydown", (event) => {
  // Eingaben in der Recovery Console (Zahlen, Text) duerfen keine Fahr- oder Zoomtasten ausloesen.
  if (isTypingTarget(event)) return;
  if (["Equal", "NumpadAdd", "Minus", "NumpadSubtract", "Digit0", "Numpad0"].includes(event.code)) {
    event.preventDefault();
    const reset = ["Digit0", "Numpad0"].includes(event.code);
    const zoomIn = ["Equal", "NumpadAdd"].includes(event.code);
    if (viewMode === "topdown") {
      if (reset) centerMapOnEgo();
      else {
        setMapFollow(false);
        zoomMapBy(zoomIn ? 1.25 : .8);
      }
    } else if (reset) {
      resetPerspectiveCamera();
    } else {
      zoomPerspectiveBy(zoomIn ? 1.2 : 1 / 1.2);
    }
    return;
  }
  if (["KeyW", "KeyA", "KeyS", "KeyD", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.code)) {
    event.preventDefault();
    keys.add(event.code);
    manualControl();
  }
});
window.addEventListener("keyup", (event) => {
  if (isTypingTarget(event)) return;
  keys.delete(event.code);
  manualControl();
});
window.addEventListener("blur", () => {
  keys.clear();
  mapPointers.clear();
  perspectivePointers.clear();
  panOrigin = null;
  pinchOrigin = null;
  perspectiveOrigin = null;
  perspectivePinchOrigin = null;
  document.querySelector(".stage").classList.remove("dragging", "rotating");
  manualControl();
});

setInterval(poll, 80);
setInterval(manualControl, 60);
setViewMode(viewMode);
setPerceptionVisible(perceptionVisible);
renderRunControl();
updateMapZoomLabel();
updateMapFollowButton();
updatePerspectiveZoomLabel();
AutonomyRecoveryVehicleAssets.load("/vehicles/ego_minibus.glb")
  .then((asset) => { egoMinibusModel.asset = asset; })
  .catch((error) => {
    egoMinibusModel.error = error;
    console.warn("Ego-Kleinbus-Asset nicht verfügbar; prozeduraler Fallback bleibt aktiv.", error);
  });
poll();
requestAnimationFrame(draw);
if (earlyRunRequested) setTimeout(() => toggleSimulationRunState("start"), 0);
