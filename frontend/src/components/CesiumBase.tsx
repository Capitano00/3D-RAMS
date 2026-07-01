import React, { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import 'cesium/Source/Widgets/widgets.css';
import { useSiteStore } from '../store/useSiteStore';

function localEnuToWgs84(x: number, z: number, latBase: number, lngBase: number) {
  const latOffset = z / 111000;
  const lngOffset = x / (111000 * Math.cos(latBase * Math.PI / 180));
  return {
    lat: latBase + latOffset,
    lng: lngBase + lngOffset
  };
}

function generateIrregularBoundary(lat: number, lng: number, radiusMeters: number = 220) {
  const points: { lat: number; lng: number }[] = [];
  const numVertices = 12;
  const seed = Math.sin(lat) * Math.cos(lng);
  for (let i = 0; i < numVertices; i++) {
    const angle = (i / numVertices) * Math.PI * 2;
    const noiseFactor = 0.82 + 0.35 * Math.abs(Math.sin(seed * (i + 1) * 45));
    const distance = radiusMeters * noiseFactor;
    
    const latOffset = (distance * Math.cos(angle)) / 111000;
    const lngOffset = (distance * Math.sin(angle)) / (111000 * Math.cos(lat * Math.PI / 180));
    points.push({ lat: lat + latOffset, lng: lng + lngOffset });
  }
  return points;
}

export const CesiumBase: React.FC = () => {
  const cesiumContainerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  
  const {
    mode,
    selectedSite,
    setFixedToEnuMatrix,
    setCesiumCameraMatrix,
    setCesiumFrustum,
    setMode,
    setResolutionProgress,
    agents,
    setAgents,
    riskZones,
  } = useSiteStore();

  // Initialize Cesium Viewer
  useEffect(() => {
    if (!cesiumContainerRef.current) return;

    // Use default Ion credentials if any, otherwise default public token
    // We disable complex widgets to keep the interface highly technical and clean
    const viewer = new Cesium.Viewer(cesiumContainerRef.current, {
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      baseLayerPicker: false,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      creditContainer: document.createElement('div'), // Hide credits bar for pristine aesthetics
    });

    // Clean viewport settings
    viewer.scene.globe.enableLighting = true;
    viewer.scene.globe.dynamicAtmosphereLighting = true;
    viewer.scene.globe.dynamicAtmosphereLightingFromSun = true;
    viewer.scene.globe.showWaterEffect = true;
    viewer.scene.globe.depthTestAgainstTerrain = true;
    viewer.scene.highDynamicRange = true;

    // Sync clock with the actual current time to map the sun's position and day/night terminator accurately
    const now = new Date();
    viewer.clock.currentTime = Cesium.JulianDate.fromDate(now);
    viewer.clock.shouldAnimate = true;
    viewer.clock.multiplier = 1.0;

    // Add star background & dark blue atmosphere feel
    viewer.scene.skyAtmosphere.show = true;
    
    // Slow default rotation when in GLOBE mode
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(selectedSite.lng, selectedSite.lat, 25000000.0),
      duration: 0.0,
    });

    viewerRef.current = viewer;

    // Set up per-frame post-render hook for camera matrix synchronization
    const onPostRender = () => {
      if (!viewerRef.current) return;
      const camera = viewerRef.current.camera;
      const frustum = camera.frustum as Cesium.PerspectiveFrustum;

      // Ensure frustum values are mapped properly
      if (frustum && typeof frustum.fovy === 'number') {
        setCesiumFrustum({
          fovy: frustum.fovy,
          aspect: frustum.aspectRatio,
          near: frustum.near,
          far: frustum.far,
        });
      }

      // Publish camera view matrix (or inverseViewMatrix which is world matrix)
      // View matrix is column-major 16-element array
      const viewMatArr = Cesium.Matrix4.toArray(camera.viewMatrix);
      const invViewMatArr = Cesium.Matrix4.toArray(camera.inverseViewMatrix);

      // Save inverse view matrix (camera's world matrix) to Zustand
      setCesiumCameraMatrix(invViewMatArr);
    };

    viewer.scene.postRender.addEventListener(onPostRender);

    return () => {
      viewer.scene.postRender.removeEventListener(onPostRender);
      viewer.destroy();
    };
  }, []);

  // Handle fly-to triggers based on Site Selection & AppMode changes
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    if (mode === 'GLOBE') {
      // Zoom out to global orbit view
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(selectedSite.lng, selectedSite.lat, 22000000.0),
        orientation: {
          heading: Cesium.Math.toRadians(0.0),
          pitch: Cesium.Math.toRadians(-90.0),
          roll: 0.0,
        },
        duration: 3.0,
      });

      setFixedToEnuMatrix(null);
    } 
    else if (mode === 'DESCENT') {
      // 1. Calculate and lock the local ENU frame anchor
      const center = Cesium.Cartesian3.fromDegrees(selectedSite.lng, selectedSite.lat, 0.0);
      const enuToFixed = Cesium.Transforms.eastNorthUpToFixedFrame(center);
      const fixedToEnu = Cesium.Matrix4.inverse(enuToFixed, new Cesium.Matrix4());
      
      // Save fixed-to-enu matrix flat elements to Zustand store
      setFixedToEnuMatrix(Cesium.Matrix4.toArray(fixedToEnu));

      // 2. Perform smooth flight descent towards site coord (1200m AGL, 55° pitch)
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(selectedSite.lng, selectedSite.lat - 0.006, 800.0),
        orientation: {
          heading: Cesium.Math.toRadians(0.0), // looking North
          pitch: Cesium.Math.toRadians(-35.0), // 35 degrees below horizon (55° pitch)
          roll: 0.0,
        },
        duration: 2.8,
        complete: () => {
          // Transition to site exploration after descent has locked in
          let progress = 0;
          const interval = setInterval(() => {
            progress += 5;
            setResolutionProgress(progress);

            // Stagger sub-agents completion
            setAgents(
              agents.map((agent) => {
                if (agent.id === 'WEATHER' && progress >= 25) return { ...agent, status: 'complete' };
                if (agent.id === 'IFA' && progress >= 50) return { ...agent, status: 'complete' };
                if (agent.id === 'OHL' && progress >= 75) return { ...agent, status: 'complete' };
                if (agent.id === 'PLANNING' && progress >= 95) return { ...agent, status: 'complete' };
                return agent;
              })
            );

            if (progress >= 100) {
              clearInterval(interval);
              setTimeout(() => {
                setMode('EXPLORATION');
              }, 400);
            }
          }, 150);
        },
      });
    }
  }, [selectedSite, mode]);

  // Handle Irregular Boundary Terrain Masking, Outline, and Choropleth Surface Color-wash
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    // Clear previous entities
    viewer.entities.removeAll();

    if (mode === 'GLOBE') {
      viewer.scene.globe.clippingPolygons = undefined as any;
      return;
    }

    // 1. Generate Irregular Review Boundary ("Floating Island" Cut-Out)
    const boundaryPoints = generateIrregularBoundary(selectedSite.lat, selectedSite.lng, 250);
    const cartesianPoints = boundaryPoints.map(p => Cesium.Cartesian3.fromDegrees(p.lng, p.lat));

    try {
      const clippingPolygon = new Cesium.ClippingPolygon({
        positions: cartesianPoints
      });
      viewer.scene.globe.clippingPolygons = new Cesium.ClippingPolygonCollection({
        polygons: [clippingPolygon],
        inverse: true, // keep inside, clip outside
        enabled: true
      });
    } catch (err) {
      console.warn('Cesium ClippingPolygon not fully supported in this context:', err);
    }

    // 2. Add Sky-500 outline along the clipped edge with PolylineGlow
    const closedCartesians = [...cartesianPoints, cartesianPoints[0]];
    viewer.entities.add({
      polyline: {
        positions: closedCartesians,
        width: 4.0,
        material: new Cesium.PolylineGlowMaterialProperty({
          glowPower: 0.2,
          color: Cesium.Color.fromCssColorString('#0ea5e9')
        }),
        clampToGround: true
      }
    });

    // 3. Render Choropleth / Color-Washed Risk Surface on Terrain
    riskZones.forEach(zone => {
      const wgs84Points = zone.points.map(pt => {
        const coords = localEnuToWgs84(pt[0], pt[1], selectedSite.lat, selectedSite.lng);
        return [coords.lng, coords.lat];
      }).flat();

      // Interpolate colors based on score
      let colorString = '#ef4444'; // default high risk red
      let opacity = 0.45;

      if (zone.score <= 0.3) {
        colorString = '#f59e0b'; // low risk amber
        opacity = 0.25;
      } else if (zone.score <= 0.6) {
        colorString = '#3b82f6'; // blue
        opacity = 0.3;
      } else if (zone.score <= 0.9) {
        colorString = '#a855f7'; // violet
        opacity = 0.35;
      }

      const cesiumColor = Cesium.Color.fromCssColorString(colorString).withAlpha(opacity);

      // Add draped classification polygon
      viewer.entities.add({
        name: zone.title,
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(wgs84Points),
          classificationType: Cesium.ClassificationType.TERRAIN,
          material: cesiumColor,
        }
      });

      // Find centroid for label placement
      let sumX = 0;
      let sumZ = 0;
      zone.points.forEach(pt => {
        sumX += pt[0];
        sumZ += pt[1];
      });
      const avgX = sumX / zone.points.length;
      const avgZ = sumZ / zone.points.length;
      const centroidWgs84 = localEnuToWgs84(avgX, avgZ, selectedSite.lat, selectedSite.lng);

      viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(centroidWgs84.lng, centroidWgs84.lat, 8.0),
        label: {
          text: `${zone.title.toUpperCase()}\nRISK: ${(zone.score * 100).toFixed(0)}%`,
          font: 'bold 9px monospace',
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          fillColor: Cesium.Color.WHITE,
          outlineColor: Cesium.Color.fromCssColorString('#0f172a'),
          outlineWidth: 3,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          disableDepthTestDistance: Number.POSITIVE_INFINITY
        }
      });
    });

  }, [selectedSite, mode, riskZones]);

  return (
    <div className="absolute inset-0 w-full h-full bg-slate-900">
      {/* Target DOM container for Cesium Canvas */}
      <div ref={cesiumContainerRef} className="w-full h-full bg-slate-900" />
    </div>
  );
};
