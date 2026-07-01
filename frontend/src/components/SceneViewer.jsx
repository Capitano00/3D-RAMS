import { useEffect, useMemo, useRef } from "react";
import { MapPinned, ShieldCheck } from "lucide-react";
import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { toList } from "../lib/uiState";
import LocalRegionOverlay from "./LocalRegionOverlay";

const REVIEW_OFFSET = {
  longitude: 0.006,
  latitude: 0.004,
};

const MARKER_STYLES = {
  evidence: {
    color: "#22d3ee",
    outline: "#0f172a",
    label: "#e0f2fe",
    size: 11,
  },
  low: {
    color: "#f59e0b",
    outline: "#0f172a",
    label: "#fef3c7",
    size: 13,
  },
  fallback: {
    color: "#a78bfa",
    outline: "#0f172a",
    label: "#ede9fe",
    size: 12,
  },
};

function hasCoordinatePair(item) {
  return Number.isFinite(Number(item?.longitude)) && Number.isFinite(Number(item?.latitude));
}

function textIncludes(item, terms) {
  const haystack = JSON.stringify(item || {}).toLowerCase();
  return terms.some((term) => haystack.includes(term));
}

function getMarkerTone(annotation) {
  if (textIncludes(annotation, ["fallback", "synthetic", "mock", "fixture"])) return "fallback";
  if (String(annotation?.confidence || "").toLowerCase() === "low") return "low";
  if (textIncludes(annotation, ["low confidence", "needs verification", "verify"])) return "low";
  return "evidence";
}

function getSceneModeLabel(scene, annotations) {
  if (textIncludes(scene, ["synthetic", "mock", "fixture"])) return "Synthetic/demo context visible";
  if (textIncludes(scene, ["fallback"])) return "Fallback scene context visible";
  if (textIncludes(scene, ["cached", "cache"])) return "Cached scene context visible";
  if (toList(annotations).some((annotation) => getMarkerTone(annotation) === "fallback")) {
    return "Includes fallback/synthetic context";
  }
  return "Live Cesium globe with token-free public imagery where available";
}

function createTokenFreeImageryProvider() {
  return new Cesium.UrlTemplateImageryProvider({
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    credit: "OpenStreetMap contributors",
    maximumLevel: 19,
  });
}

function addReviewBoundary(viewer, center) {
  viewer.entities.add({
    name: "Review area",
    polygon: {
      hierarchy: Cesium.Cartesian3.fromDegreesArray([
        center.longitude - REVIEW_OFFSET.longitude,
        center.latitude - REVIEW_OFFSET.latitude,
        center.longitude + REVIEW_OFFSET.longitude,
        center.latitude - REVIEW_OFFSET.latitude,
        center.longitude + REVIEW_OFFSET.longitude,
        center.latitude + REVIEW_OFFSET.latitude,
        center.longitude - REVIEW_OFFSET.longitude,
        center.latitude + REVIEW_OFFSET.latitude,
      ]),
      height: 0,
      material: Cesium.Color.fromCssColorString("#0891b2").withAlpha(0.18),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString("#22d3ee").withAlpha(0.86),
    },
  });
}

function addSelectedSiteMarker(viewer, center, location) {
  viewer.entities.add({
    name: location?.label || "Selected site",
    position: Cesium.Cartesian3.fromDegrees(center.longitude, center.latitude, 42),
    point: {
      pixelSize: 16,
      color: Cesium.Color.fromCssColorString("#38bdf8"),
      outlineColor: Cesium.Color.fromCssColorString("#e0f2fe"),
      outlineWidth: 3,
    },
    label: {
      text: location?.label || "Selected site",
      font: "700 13px Inter, system-ui, sans-serif",
      fillColor: Cesium.Color.fromCssColorString("#f8fafc"),
      outlineColor: Cesium.Color.fromCssColorString("#020617"),
      outlineWidth: 4,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      showBackground: true,
      backgroundColor: Cesium.Color.fromCssColorString("#0f172a").withAlpha(0.82),
      pixelOffset: new Cesium.Cartesian2(0, -32),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });
}

function addAnnotationMarkers(viewer, annotations) {
  toList(annotations)
    .filter(hasCoordinatePair)
    .forEach((annotation) => {
      const tone = getMarkerTone(annotation);
      const style = MARKER_STYLES[tone];

      viewer.entities.add({
        name: annotation.title || "Risk annotation",
        position: Cesium.Cartesian3.fromDegrees(Number(annotation.longitude), Number(annotation.latitude), 36),
        point: {
          pixelSize: style.size,
          color: Cesium.Color.fromCssColorString(style.color),
          outlineColor: Cesium.Color.fromCssColorString(style.outline),
          outlineWidth: 3,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        label: {
          text: annotation.title || "Risk annotation",
          font: "700 12px Inter, system-ui, sans-serif",
          fillColor: Cesium.Color.fromCssColorString(style.label),
          outlineColor: Cesium.Color.fromCssColorString("#020617"),
          outlineWidth: 4,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          showBackground: true,
          backgroundColor: Cesium.Color.fromCssColorString("#0b1120").withAlpha(0.76),
          pixelOffset: new Cesium.Cartesian2(0, -24),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
    });
}

function addAccessRoutes(viewer, scene) {
  const routes = toList(scene?.accessRoutes || scene?.accessRoute);

  routes.forEach((route, index) => {
    const points = toList(route?.points || route).filter(hasCoordinatePair);
    if (points.length < 2) return;

    viewer.entities.add({
      name: route?.label || `Access route ${index + 1}`,
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArray(
          points.flatMap((point) => [Number(point.longitude), Number(point.latitude)]),
        ),
        width: 3,
        material: Cesium.Color.fromCssColorString("#60a5fa").withAlpha(0.84),
        clampToGround: true,
      },
    });
  });
}

function fromOffsets(center, offsets) {
  return offsets.flatMap(([longitudeOffset, latitudeOffset]) => [
    center.longitude + longitudeOffset,
    center.latitude + latitudeOffset,
  ]);
}

function addLayerLabel(viewer, center, longitudeOffset, latitudeOffset, text, color) {
  viewer.entities.add({
    name: text,
    position: Cesium.Cartesian3.fromDegrees(center.longitude + longitudeOffset, center.latitude + latitudeOffset, 62),
    label: {
      text,
      font: "700 12px Inter, system-ui, sans-serif",
      fillColor: Cesium.Color.fromCssColorString(color),
      outlineColor: Cesium.Color.WHITE,
      outlineWidth: 4,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      showBackground: true,
      backgroundColor: Cesium.Color.WHITE.withAlpha(0.78),
      pixelOffset: new Cesium.Cartesian2(0, -8),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });
}

function addTerrainReliefTiles(viewer, center) {
  const tiles = [
    { x: -0.0045, y: -0.0028, h: 18, c: "#d8efe5" },
    { x: -0.0015, y: -0.0028, h: 34, c: "#c5e4d2" },
    { x: 0.0015, y: -0.0028, h: 24, c: "#d8ead8" },
    { x: 0.0045, y: -0.0028, h: 42, c: "#b8dcc1" },
    { x: -0.0045, y: 0, h: 26, c: "#d5e9d5" },
    { x: -0.0015, y: 0, h: 62, c: "#a9d4b6" },
    { x: 0.0015, y: 0, h: 48, c: "#bfe0c8" },
    { x: 0.0045, y: 0, h: 30, c: "#d9ead4" },
    { x: -0.0045, y: 0.0028, h: 52, c: "#b3d9c0" },
    { x: -0.0015, y: 0.0028, h: 78, c: "#93c5a5" },
    { x: 0.0015, y: 0.0028, h: 58, c: "#aad3b5" },
    { x: 0.0045, y: 0.0028, h: 36, c: "#c9e6cf" },
  ];

  tiles.forEach((tile, index) => {
    const halfLon = 0.00135;
    const halfLat = 0.0012;
    viewer.entities.add({
      name: `Local terrain evidence tile ${index + 1}`,
      polygon: {
        hierarchy: Cesium.Cartesian3.fromDegreesArray([
          center.longitude + tile.x - halfLon,
          center.latitude + tile.y - halfLat,
          center.longitude + tile.x + halfLon,
          center.latitude + tile.y - halfLat,
          center.longitude + tile.x + halfLon,
          center.latitude + tile.y + halfLat,
          center.longitude + tile.x - halfLon,
          center.latitude + tile.y + halfLat,
        ]),
        height: 0,
        extrudedHeight: tile.h,
        material: Cesium.Color.fromCssColorString(tile.c).withAlpha(0.78),
        outline: true,
        outlineColor: Cesium.Color.fromCssColorString("#ffffff").withAlpha(0.82),
      },
    });
  });
}

function addWeatherAndResourceSignals(viewer, center) {
  const rainCells = [
    [-0.0038, 0.0025, 120],
    [-0.0025, 0.0016, 86],
    [-0.0008, 0.0028, 104],
    [0.0012, 0.0015, 68],
  ];

  rainCells.forEach(([longitudeOffset, latitudeOffset, height], index) => {
    viewer.entities.add({
      name: `Rainfall intensity column ${index + 1}`,
      position: Cesium.Cartesian3.fromDegrees(center.longitude + longitudeOffset, center.latitude + latitudeOffset, height / 2),
      cylinder: {
        length: height,
        topRadius: 45,
        bottomRadius: 45,
        material: Cesium.Color.fromCssColorString("#38bdf8").withAlpha(0.24),
        outline: true,
        outlineColor: Cesium.Color.fromCssColorString("#0284c7").withAlpha(0.55),
      },
    });
  });

  const windVectors = [
    [-0.0046, -0.0031, -0.0012, -0.0012],
    [-0.0018, -0.0032, 0.0016, -0.0011],
    [0.0012, -0.0031, 0.0048, -0.0014],
  ];

  windVectors.forEach(([startLon, startLat, endLon, endLat], index) => {
    viewer.entities.add({
      name: `Wind vector ${index + 1}`,
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArrayHeights([
          center.longitude + startLon,
          center.latitude + startLat,
          95,
          center.longitude + endLon,
          center.latitude + endLat,
          95,
        ]),
        width: 7,
        material: new Cesium.PolylineArrowMaterialProperty(
          Cesium.Color.fromCssColorString("#60a5fa").withAlpha(0.78),
        ),
      },
    });
  });
}

function addAssessmentRegionLayers(viewer, center) {
  addTerrainReliefTiles(viewer, center);

  viewer.entities.add({
    name: "Water and flooding context layer",
    polygon: {
      hierarchy: Cesium.Cartesian3.fromDegreesArray(
        fromOffsets(center, [
          [-0.0055, -0.0036],
          [-0.001, -0.0036],
          [-0.0002, 0.0035],
          [-0.0055, 0.0035],
        ]),
      ),
      height: 4,
      material: Cesium.Color.fromCssColorString("#38bdf8").withAlpha(0.28),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString("#0284c7").withAlpha(0.86),
    },
  });

  viewer.entities.add({
    name: "Access route context",
    polyline: {
      positions: Cesium.Cartesian3.fromDegreesArray(
        fromOffsets(center, [
          [-0.0058, -0.0026],
          [-0.003, -0.0012],
          [-0.0008, 0.0004],
          [0.0038, 0.0028],
        ]),
      ),
      width: 5,
      material: Cesium.Color.fromCssColorString("#22c55e").withAlpha(0.86),
      clampToGround: false,
    },
  });

  viewer.entities.add({
    name: "Infrastructure and utility corridor",
    polyline: {
      positions: Cesium.Cartesian3.fromDegreesArray(
        fromOffsets(center, [
          [-0.0048, 0.003],
          [-0.0015, 0.0013],
          [0.0018, -0.0006],
          [0.0052, -0.0028],
        ]),
      ),
      width: 4,
      material: Cesium.Color.fromCssColorString("#f59e0b").withAlpha(0.9),
      clampToGround: false,
    },
  });

  viewer.entities.add({
    name: "Fallback or utility verification corridor",
    polyline: {
      positions: Cesium.Cartesian3.fromDegreesArray(
        fromOffsets(center, [
          [-0.0044, -0.0002],
          [-0.0002, 0.0012],
          [0.0046, 0.0006],
        ]),
      ),
      width: 3,
      material: Cesium.Color.fromCssColorString("#8b5cf6").withAlpha(0.86),
      clampToGround: false,
    },
  });

  viewer.entities.add({
    name: "Human verification focus",
    position: Cesium.Cartesian3.fromDegrees(center.longitude + 0.0018, center.latitude - 0.0014, 12),
    ellipse: {
      semiMajorAxis: 180,
      semiMinorAxis: 110,
      material: Cesium.Color.fromCssColorString("#f59e0b").withAlpha(0.2),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString("#f59e0b").withAlpha(0.9),
    },
  });

  addLayerLabel(viewer, center, -0.0042, 0.0028, "Water / flood context", "#0369a1");
  addLayerLabel(viewer, center, -0.002, 0.0016, "Rainfall signal", "#0284c7");
  addLayerLabel(viewer, center, 0.002, -0.0022, "Wind exposure", "#2563eb");
  addLayerLabel(viewer, center, 0.0032, 0.0028, "Access route", "#15803d");
  addLayerLabel(viewer, center, 0.0036, -0.0028, "Utility / infrastructure", "#92400e");
  addLayerLabel(viewer, center, 0.0018, -0.0014, "Verify on site", "#b45309");
  addWeatherAndResourceSignals(viewer, center);
}

function configureFutureTerrainProvider() {
  // Future: add token-free terrain from approved local/static providers when available.
}

function addFuture3DTilesLayer() {
  // Future: attach approved 3D Tiles only when the demo has a token-free or cleared data source.
}

function addInfrastructureCorridors() {
  // Future: map rail, road, power, telecom, or utility corridors from verified backend layers.
}

function addOverheadLineBuffers() {
  // Future: render OHL clearance and buffer volumes when the backend provides geometry.
}

function addFloodWaterOverlays() {
  // Future: render flood, drainage, and surface-water overlays from verified or clearly labelled data.
}

function prepareEvidenceScreenshotExport() {
  // Future: export annotated screenshots with evidence IDs for human review packs.
}

export default function SceneViewer({ scene, annotations, location }) {
  const containerRef = useRef(null);
  const mappedAnnotations = useMemo(() => toList(annotations).filter(hasCoordinatePair), [annotations]);
  const sceneModeLabel = useMemo(() => getSceneModeLabel(scene, mappedAnnotations), [scene, mappedAnnotations]);

  useEffect(() => {
    if (!containerRef.current || !scene?.center) return undefined;

    Cesium.Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_ION_TOKEN || "";
    const viewer = new Cesium.Viewer(containerRef.current, {
      animation: false,
      timeline: false,
      imageryProvider: createTokenFreeImageryProvider(),
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      baseLayerPicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      scene3DOnly: true,
    });

    viewer.scene.backgroundColor = Cesium.Color.fromCssColorString("#e8f3f7");
    viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#bfd7d2");
    viewer.scene.globe.enableLighting = true;
    viewer.scene.globe.showWaterEffect = true;
    viewer.scene.skyAtmosphere.show = true;
    viewer.scene.fog.enabled = false;
    viewer.scene.screenSpaceCameraController.enableCollisionDetection = false;

    const center = scene.center;
    addReviewBoundary(viewer, center);
    addAssessmentRegionLayers(viewer, center);
    addSelectedSiteMarker(viewer, center, location);
    addAnnotationMarkers(viewer, mappedAnnotations);
    addAccessRoutes(viewer, scene);

    configureFutureTerrainProvider(viewer, scene);
    addFuture3DTilesLayer(viewer, scene);
    addInfrastructureCorridors(viewer, scene);
    addOverheadLineBuffers(viewer, scene);
    addFloodWaterOverlays(viewer, scene);
    prepareEvidenceScreenshotExport(viewer, scene);

    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(center.longitude, center.latitude, 1500),
      orientation: {
        heading: Cesium.Math.toRadians(scene.camera?.headingDegrees || 0),
        pitch: Cesium.Math.toRadians(scene.camera?.pitchDegrees || -48),
      },
      duration: 0,
    });

    return () => {
      if (!viewer.isDestroyed()) viewer.destroy();
    };
  }, [scene, mappedAnnotations, location]);

  if (!scene) {
    return (
      <div className="empty-map risk-scene-empty">
        <MapPinned size={24} />
        <span>Map updates after the agent resolves a site.</span>
      </div>
    );
  }

  return (
    <div className="scene-shell risk-scene-shell">
      <div ref={containerRef} className="scene-viewer risk-scene-viewer" />
      <LocalRegionOverlay active={Boolean(scene?.center)} />
      <div className="scene-legend" aria-label="Scene legend">
        <div className="scene-legend-item">
          <span className="legend-swatch review" />
          Review area
        </div>
        <div className="scene-legend-item">
          <span className="legend-swatch water" />
          Water / flooding context
        </div>
        <div className="scene-legend-item">
          <span className="legend-swatch access" />
          Access route context
        </div>
        <div className="scene-legend-item">
          <span className="legend-swatch utility" />
          Utility / infrastructure corridor
        </div>
        <div className="scene-legend-item">
          <span className="legend-swatch weather" />
          Rain / wind signal
        </div>
        <div className="scene-legend-item">
          <span className="legend-swatch evidence" />
          Evidence-backed marker
        </div>
        <div className="scene-legend-item">
          <span className="legend-swatch low" />
          Low-confidence / needs verification
        </div>
        <div className="scene-legend-item">
          <span className="legend-swatch fallback" />
          Fallback or synthetic context
        </div>
        <div className="scene-legend-item">
          <ShieldCheck size={13} />
          Human review required
        </div>
      </div>
      <div className="map-caption risk-scene-caption">
        <strong>{location?.label || "Selected site"}</strong>
        <span>{mappedAnnotations.length} mapped marker(s)</span>
        <span>{sceneModeLabel}</span>
        <span>Inspectable pre-visit scene, not work approval.</span>
      </div>
    </div>
  );
}
