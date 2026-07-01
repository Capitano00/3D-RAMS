import { useEffect, useMemo, useRef, useState } from "react";
import { MapPinned } from "lucide-react";
import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import "./site-scene.css";

function toList(value) {
  return Array.isArray(value) ? value : [];
}

function numericValue(...values) {
  for (const value of values) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function normalizeCenter(scene) {
  const latitude = numericValue(scene?.center?.latitude, scene?.center?.lat, scene?.latitude, scene?.lat);
  const longitude = numericValue(scene?.center?.longitude, scene?.center?.lng, scene?.center?.lon, scene?.longitude, scene?.lng, scene?.lon);
  if (latitude === null || longitude === null) return null;
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null;
  return { latitude, longitude };
}

function normalizeAnnotation(annotation, index) {
  const latitude = numericValue(annotation?.latitude, annotation?.lat, annotation?.location?.latitude, annotation?.location?.lat);
  const longitude = numericValue(
    annotation?.longitude,
    annotation?.lng,
    annotation?.lon,
    annotation?.location?.longitude,
    annotation?.location?.lng,
    annotation?.location?.lon,
  );
  if (latitude === null || longitude === null) return null;
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null;
  return {
    id: annotation?.id || annotation?.evidenceId || `${annotation?.title || "annotation"}-${index}`,
    title: annotation?.title || annotation?.label || "Review marker",
    confidence: annotation?.confidence || "review",
    sourceType: annotation?.sourceType || annotation?.source || annotation?.dataMode || "source pending",
    latitude,
    longitude,
  };
}

function safeStatusClass(status) {
  if (status.includes("terrain-backed")) return "terrain";
  if (status.includes("synthetic")) return "synthetic";
  if (status.includes("unavailable")) return "unavailable";
  return "pending";
}

function getAnnotationColor(CesiumApi, confidence) {
  if (confidence === "low" || confidence === "review") return CesiumApi.Color.fromCssColorString("#b45309");
  if (confidence === "high") return CesiumApi.Color.fromCssColorString("#0b6f65");
  return CesiumApi.Color.fromCssColorString("#1d4ed8");
}

async function buildTerrainProvider() {
  if (typeof Cesium.createWorldTerrainAsync === "function") {
    return Cesium.createWorldTerrainAsync({
      requestVertexNormals: true,
      requestWaterMask: true,
    });
  }
  return undefined;
}

async function addIonImageryLayer(viewer) {
  if (typeof Cesium.createWorldImageryAsync !== "function") return false;
  const imageryProvider = await Cesium.createWorldImageryAsync();
  viewer.imageryLayers.removeAll();
  viewer.imageryLayers.addImageryProvider(imageryProvider);
  return true;
}

function addReviewPolygon(viewer, center, terrainBacked) {
  viewer.entities.add({
    name: "Review area",
    polygon: {
      hierarchy: Cesium.Cartesian3.fromDegreesArray([
        center.longitude - 0.006,
        center.latitude - 0.004,
        center.longitude + 0.006,
        center.latitude - 0.004,
        center.longitude + 0.006,
        center.latitude + 0.004,
        center.longitude - 0.006,
        center.latitude + 0.004,
      ]),
      material: Cesium.Color.fromCssColorString(terrainBacked ? "#3ba99c" : "#7fb9a7").withAlpha(0.32),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString("#0b6f65"),
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
    },
  });
}

function addAnnotationMarkers(viewer, annotations) {
  annotations.forEach((annotation) => {
    viewer.entities.add({
      name: annotation.title,
      position: Cesium.Cartesian3.fromDegrees(annotation.longitude, annotation.latitude, 24),
      point: {
        pixelSize: annotation.confidence === "low" ? 12 : 10,
        color: getAnnotationColor(Cesium, annotation.confidence),
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      },
      label: {
        text: annotation.title,
        font: "12px sans-serif",
        fillColor: Cesium.Color.fromCssColorString("#111827"),
        showBackground: true,
        backgroundColor: Cesium.Color.WHITE.withAlpha(0.86),
        pixelOffset: new Cesium.Cartesian2(0, -22),
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
  });
}

function SyntheticScene({ center, annotations, location, status, reason }) {
  const clampPercent = (value) => Math.min(94, Math.max(6, value));
  const markerStyle = (annotation) => ({
    left: `${clampPercent(50 + (annotation.longitude - center.longitude) * 4200)}%`,
    top: `${clampPercent(50 - (annotation.latitude - center.latitude) * 5400)}%`,
  });

  return (
    <div className="site-scene-shell site-scene-synthetic" role="img" aria-label="Synthetic 3D scene fallback">
      <div className={`site-scene-status ${safeStatusClass(status)}`}>{status}</div>
      <div className="site-scene-synthetic-surface">
        <div className="site-scene-review-polygon" />
        <div className="site-scene-center-pin" title="Review centre" />
        {annotations.map((annotation) => (
          <div className="site-scene-marker" style={markerStyle(annotation)} title={annotation.title} key={annotation.id}>
            <span>{annotation.title}</span>
          </div>
        ))}
      </div>
      <div className="site-scene-caption">
        <strong>{location?.label || "Selected site"}</strong>
        <span>{reason || "Synthetic fallback only. No real terrain, imagery, or live hazards are shown."}</span>
        <small>{annotations.length} mapped review marker(s)</small>
      </div>
    </div>
  );
}

export function SiteSceneViewer({ scene, annotations, location }) {
  const containerRef = useRef(null);
  const [renderError, setRenderError] = useState("");
  const [renderStatus, setRenderStatus] = useState("waiting for confirmed location");

  const center = useMemo(() => normalizeCenter(scene), [scene]);
  const validAnnotations = useMemo(
    () => toList(annotations).map(normalizeAnnotation).filter(Boolean),
    [annotations],
  );
  const skippedAnnotationCount = toList(annotations).length - validAnnotations.length;
  const ionToken = (import.meta.env.VITE_CESIUM_ION_TOKEN || "").trim();

  useEffect(() => {
    setRenderError("");
    if (!scene) {
      setRenderStatus("waiting for confirmed location");
      return undefined;
    }
    if (!center) {
      setRenderStatus("renderer unavailable: missing scene center");
      return undefined;
    }
    if (!ionToken) {
      setRenderStatus("3D fallback: synthetic scene only");
      return undefined;
    }
    if (!containerRef.current || typeof Cesium?.Viewer !== "function") {
      setRenderStatus("renderer unavailable");
      setRenderError("Cesium viewer APIs are not available in this browser build.");
      return undefined;
    }

    let viewer;
    let disposed = false;
    setRenderStatus("terrain-backed scene loading");

    async function initialiseViewer() {
      try {
        Cesium.Ion.defaultAccessToken = ionToken;
        const terrainProvider = await buildTerrainProvider();
        if (!terrainProvider) {
          throw new Error("Cesium terrain APIs are not available in this build.");
        }
        if (disposed) return;

        viewer = new Cesium.Viewer(containerRef.current, {
          animation: false,
          timeline: false,
          geocoder: false,
          homeButton: false,
          sceneModePicker: false,
          baseLayerPicker: false,
          navigationHelpButton: false,
          fullscreenButton: false,
          infoBox: false,
          selectionIndicator: false,
          terrainProvider,
        });

        viewer.scene.globe.depthTestAgainstTerrain = true;
        viewer.scene.fog.enabled = false;
        viewer.scene.skyAtmosphere.show = true;
        viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#dfe8e4");

        try {
          await addIonImageryLayer(viewer);
        } catch {
          viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#cbd8d2");
        }

        if (disposed) return;
        addReviewPolygon(viewer, center, Boolean(terrainProvider));
        addAnnotationMarkers(viewer, validAnnotations);

        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(center.longitude, center.latitude, scene?.camera?.heightMeters || 1500),
          orientation: {
            heading: Cesium.Math.toRadians(scene?.camera?.headingDegrees || 0),
            pitch: Cesium.Math.toRadians(scene?.camera?.pitchDegrees || -48),
          },
          duration: 0,
        });

        setRenderStatus("terrain-backed scene");
      } catch (err) {
        setRenderError(err?.message || "Cesium scene renderer failed.");
        setRenderStatus("renderer unavailable");
        if (viewer && !viewer.isDestroyed()) viewer.destroy();
        viewer = null;
      }
    }

    initialiseViewer();

    return () => {
      disposed = true;
      if (viewer && !viewer.isDestroyed()) viewer.destroy();
    };
  }, [scene, center, validAnnotations, ionToken]);

  if (!scene) {
    return (
      <div className="site-scene-empty">
        <MapPinned size={24} />
        <strong>waiting for confirmed location</strong>
        <span>Confirm a candidate site or provide a coordinate, postcode, nearest town, or supported fixture before map tools run.</span>
      </div>
    );
  }

  if (!center) {
    return (
      <div className="site-scene-fallback">
        <div className="site-scene-status unavailable">renderer unavailable: missing scene center</div>
        <MapPinned size={28} />
        <h3>{location?.label || "Selected site"}</h3>
        <p>The scene payload did not include a valid latitude/longitude center. No terrain, imagery, or synthetic markers are shown.</p>
      </div>
    );
  }

  if (!ionToken) {
    return (
      <SyntheticScene
        center={center}
        annotations={validAnnotations}
        location={location}
        status="3D fallback: synthetic scene only"
        reason="No Cesium Ion token is configured. This is a synthetic review surface, not real terrain or imagery."
      />
    );
  }

  if (renderError) {
    return (
      <SyntheticScene
        center={center}
        annotations={validAnnotations}
        location={location}
        status="renderer unavailable"
        reason={`Cesium renderer failed: ${renderError}. Showing synthetic fallback only.`}
      />
    );
  }

  return (
    <div className="site-scene-shell">
      <div className={`site-scene-status ${safeStatusClass(renderStatus)}`}>{renderStatus}</div>
      <div ref={containerRef} className="site-scene-viewer" />
      <div className="site-scene-caption">
        <strong>{location?.label || "Selected site"}</strong>
        <span>{validAnnotations.length} mapped review marker(s)</span>
        {skippedAnnotationCount > 0 && <small>{skippedAnnotationCount} marker(s) skipped: missing coordinates</small>}
        {(location?.confidence || location?.dataMode) && (
          <small>{[location.confidence, location.dataMode].filter(Boolean).join(" - ")}</small>
        )}
      </div>
    </div>
  );
}

export { SiteSceneViewer as SceneViewer };
export default SiteSceneViewer;
