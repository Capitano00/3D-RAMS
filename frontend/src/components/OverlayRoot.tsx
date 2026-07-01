import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { useSiteStore } from '../store/useSiteStore';
import { Annotation } from '../types';

export const OverlayRoot: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const {
    mode,
    selectedSite,
    fixedToEnuMatrix,
    cesiumCameraMatrix,
    cesiumFrustum,
    annotations,
    selectedAnnotation,
    setSelectedAnnotation,
    weatherActive,
    resolutionProgress,
    riskZones,
  } = useSiteStore();

  // Hover states to overlay text tooltip
  const [hoveredObjectName, setHoveredObjectName] = useState<string | null>(null);

  // References
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);

  // Groups and meshes
  const overlayGroupRef = useRef<THREE.Group | null>(null);
  const satelliteGroupRef = useRef<THREE.Group | null>(null);
  const pylonGroupRef = useRef<THREE.Group | null>(null);
  const treeGroupRef = useRef<THREE.Group | null>(null);
  const cloudGroupRef = useRef<THREE.Group | null>(null);
  const rainRef = useRef<THREE.Points | null>(null);
  
  // Interactive lists
  const interactivePinsRef = useRef<{ mesh: THREE.Mesh; annotation: Annotation }[]>([]);
  const satelliteCoresRef = useRef<{ mesh: THREE.Mesh; agentId: string }[]>([]);
  const riskPrismsRef = useRef<{ mesh: THREE.Mesh; annotationId: string; category: string; score: number }[]>([]);

  // 1. Procedural Site Core Grid Texture for flat ground proxy representation
  const createLocalGroundTexture = (): THREE.CanvasTexture => {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 512;
    const ctx = canvas.getContext('2d')!;

    // Ensure transparent background (no background rect filled, letting Cesium show through)
    ctx.clearRect(0, 0, 512, 512);

    // Subtle terrain land contours
    ctx.strokeStyle = 'rgba(30, 41, 59, 0.35)';
    ctx.lineWidth = 1.5;
    for (let i = 0; i < 5; i++) {
      ctx.beginPath();
      ctx.arc(256, 256, 50 + i * 80, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Worksite gravel/dirt corridor - transparent overlay
    ctx.fillStyle = 'rgba(30, 41, 59, 0.25)';
    ctx.fillRect(100, 0, 312, 512);

    // Main central rail tracks (representing Infrastructure context)
    ctx.fillStyle = 'rgba(15, 23, 42, 0.35)';
    ctx.fillRect(240, 0, 32, 512);

    // Rail steel tracks
    ctx.fillStyle = '#64748b';
    ctx.fillRect(245, 0, 3, 512);
    ctx.fillRect(264, 0, 3, 512);

    // Tech grid overlay
    ctx.strokeStyle = 'rgba(0, 229, 255, 0.12)';
    ctx.lineWidth = 1;
    for (let i = 0; i < 512; i += 32) {
      ctx.beginPath();
      ctx.moveTo(i, 0);
      ctx.lineTo(i, 512);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, i);
      ctx.lineTo(512, i);
      ctx.stroke();
    }

    // Yellow warning hazard box boundary
    ctx.strokeStyle = '#eab308';
    ctx.setLineDash([8, 8]);
    ctx.lineWidth = 2.5;
    ctx.strokeRect(50, 120, 150, 160);
    ctx.setLineDash([]);

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  };

  // ThreeJS initialization
  useEffect(() => {
    if (!canvasRef.current || !containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight || 600;

    // SCENE
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // CAMERA (Custom sync, manually updated view matrices)
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 5000);
    camera.matrixAutoUpdate = false; // ENU Local-origin camera sync override
    cameraRef.current = camera;

    // RENDERER
    const renderer = new THREE.WebGLRenderer({
      canvas: canvasRef.current,
      antialias: true,
      alpha: true, // critical to overlay transparently over Cesium canvas
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    rendererRef.current = renderer;

    // LIGHTS (Synced to worksite region)
    const ambientLight = new THREE.AmbientLight('#ffffff', 0.8);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight('#ffffff', 1.5);
    dirLight.position.set(30, 80, 20);
    scene.add(dirLight);

    // Spot scanning light
    const spotLight = new THREE.SpotLight('#00e5ff', 4, 120, Math.PI / 4, 0.5, 1);
    spotLight.position.set(0, 70, 0);
    scene.add(spotLight);

    // ----------------------------------------------------
    // OVERLAY ROOT GROUP (Local Origin - 0,0,0 as site anchor)
    // ----------------------------------------------------
    const overlayGroup = new THREE.Group();
    scene.add(overlayGroup);
    overlayGroupRef.current = overlayGroup;

    // 1. Semi-transparent ground plate proxy
    const groundGeo = new THREE.PlaneGeometry(120, 120, 32, 32);
    const groundMat = new THREE.MeshStandardMaterial({
      map: createLocalGroundTexture(),
      transparent: true,
      opacity: 0.85,
      roughness: 0.9,
      metalness: 0.1,
      flatShading: true,
    });
    const groundMesh = new THREE.Mesh(groundGeo, groundMat);
    groundMesh.rotation.x = -Math.PI / 2;
    groundMesh.position.y = 0.05; // slightly above base
    overlayGroup.add(groundMesh);

    // 2. Holographic Scanning Disc (State B: Descent & Scan)
    const scanDiscGeo = new THREE.RingGeometry(0.1, 40, 64);
    const scanDiscMat = new THREE.MeshBasicMaterial({
      color: '#00e5ff',
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.15,
      wireframe: true,
    });
    const scanDisc = new THREE.Mesh(scanDiscGeo, scanDiscMat);
    scanDisc.rotation.x = -Math.PI / 2;
    scanDisc.position.y = 0.1;
    overlayGroup.add(scanDisc);

    // Outer thick pulse circle
    const outerScanRingGeo = new THREE.RingGeometry(39.5, 40, 64);
    const outerScanRingMat = new THREE.MeshBasicMaterial({
      color: '#00e5ff',
      transparent: true,
      opacity: 0.4,
      side: THREE.DoubleSide,
    });
    const outerScanRing = new THREE.Mesh(outerScanRingGeo, outerScanRingMat);
    outerScanRing.rotation.x = -Math.PI / 2;
    outerScanRing.position.y = 0.11;
    overlayGroup.add(outerScanRing);

    // 3. LOW-POLY STYLIZATION (Buildings, Pylons, Cables, Trees)
    
    // Extruded matte ceramic buildings
    const buildBuilding = (w: number, h: number, d: number, color: string, pos: [number, number, number]): THREE.Group => {
      const bGroup = new THREE.Group();
      bGroup.position.set(pos[0], pos[1], pos[2]);

      // Main structure block
      const structGeo = new THREE.BoxGeometry(w, h, d);
      const structMat = new THREE.MeshStandardMaterial({ color, flatShading: true, roughness: 0.8 });
      const structMesh = new THREE.Mesh(structGeo, structMat);
      structMesh.position.y = h / 2;
      bGroup.add(structMesh);

      // Low poly pitched roof
      const roofGeo = new THREE.ConeGeometry(Math.max(w, d) * 0.7, 3, 4);
      const roofMat = new THREE.MeshStandardMaterial({ color: '#334155', flatShading: true });
      const roofMesh = new THREE.Mesh(roofGeo, roofMat);
      roofMesh.position.y = h + 1.5;
      roofMesh.rotation.y = Math.PI / 4;
      bGroup.add(roofMesh);

      overlayGroup.add(bGroup);
      return bGroup;
    };

    // Instantiate worksite infrastructure modules
    const substation = buildBuilding(10, 6, 8, '#cfd8dc', [-15, 0, -10]);
    const cabin = buildBuilding(6, 4, 4, '#78909c', [15, 0, 15]);

    // Low-Poly Pylons & Overhead Conductor splines
    const pylonGroup = new THREE.Group();
    overlayGroup.add(pylonGroup);
    pylonGroupRef.current = pylonGroup;

    const buildPylon = (): THREE.Group => {
      const pylon = new THREE.Group();
      const height = 18;
      const baseSize = 2.4;
      const topSize = 0.8;

      const latticeGeo = new THREE.CylinderGeometry(topSize, baseSize, height, 4, 4, true);
      const wireMat = new THREE.MeshStandardMaterial({
        color: '#475569',
        flatShading: true,
        wireframe: true,
      });
      const lattice = new THREE.Mesh(latticeGeo, wireMat);
      lattice.position.y = height / 2;
      pylon.add(lattice);

      // Solid inner chassis
      const innerGeo = new THREE.CylinderGeometry(topSize * 0.85, baseSize * 0.85, height, 4, 1);
      const innerMat = new THREE.MeshStandardMaterial({ color: '#1e293b', flatShading: true });
      const inner = new THREE.Mesh(innerGeo, innerMat);
      inner.position.y = height / 2;
      pylon.add(inner);

      // Pylon arm supports
      const armWidth = 7;
      const armGeo = new THREE.BoxGeometry(armWidth, 0.4, 0.4);
      const armMat = new THREE.MeshStandardMaterial({ color: '#475569', flatShading: true });

      const arm1 = new THREE.Mesh(armGeo, armMat);
      arm1.position.set(0, height * 0.7, 0);
      pylon.add(arm1);

      const arm2 = new THREE.Mesh(armGeo, armMat);
      arm2.position.set(0, height * 0.9, 0);
      pylon.add(arm2);

      // Conductor terminal isolators (glass rings)
      const isoGeo = new THREE.CylinderGeometry(0.18, 0.18, 1.2, 5);
      const isoMat = new THREE.MeshStandardMaterial({
        color: '#eab308',
        emissive: '#eab308',
        emissiveIntensity: 0.5,
      });

      const isoCoords = [
        [-armWidth / 2, height * 0.7 - 0.6, 0],
        [armWidth / 2, height * 0.7 - 0.6, 0],
        [-armWidth / 2, height * 0.9 - 0.6, 0],
        [armWidth / 2, height * 0.9 - 0.6, 0],
      ];

      isoCoords.forEach((coord) => {
        const iso = new THREE.Mesh(isoGeo, isoMat);
        iso.position.set(coord[0], coord[1], coord[2]);
        pylon.add(iso);
      });

      return pylon;
    };

    // Instantiate pylons along corridor vectors
    const pylon1 = buildPylon();
    pylon1.position.set(-35, 0, -5);
    pylonGroup.add(pylon1);

    const pylon2 = buildPylon();
    pylon2.position.set(0, 0, -5);
    pylonGroup.add(pylon2);

    const pylon3 = buildPylon();
    pylon3.position.set(35, 0, -5);
    pylonGroup.add(pylon3);

    const pylonsList = [pylon1, pylon2, pylon3];
    const armOffsets = [
      [-3.5, 12, 0],
      [3.5, 12, 0],
      [-3.5, 15.6, 0],
      [3.5, 15.6, 0],
    ];

    // Build Overhead bezier cable lines
    armOffsets.forEach((offset) => {
      for (let p = 0; p < 2; p++) {
        const py1 = pylonsList[p];
        const py2 = pylonsList[p + 1];

        const startPos = new THREE.Vector3(
          py1.position.x + offset[0],
          py1.position.y + offset[1],
          py1.position.z + offset[2]
        );
        const endPos = new THREE.Vector3(
          py2.position.x + offset[0],
          py2.position.y + offset[1],
          py2.position.z + offset[2]
        );

        const mid = new THREE.Vector3().addVectors(startPos, endPos).multiplyScalar(0.5);
        mid.y -= 1.8; // sag clearance variance

        const bezier = new THREE.QuadraticBezierCurve3(startPos, mid, endPos);
        const points = bezier.getPoints(24);
        const cableGeo = new THREE.BufferGeometry().setFromPoints(points);

        const cableMat = new THREE.LineBasicMaterial({
          color: '#eab308',
          linewidth: 2,
        });
        const cableLine = new THREE.Line(cableGeo, cableMat);
        pylonGroup.add(cableLine);

        // Render transparent collision warning buffer cylinders around cable segments
        const segmentLen = startPos.distanceTo(endPos);
        const bufferGeo = new THREE.CylinderGeometry(2.8, 2.8, segmentLen, 6, 1, true);
        const bufferMat = new THREE.MeshBasicMaterial({
          color: '#eab308',
          transparent: true,
          opacity: 0.05,
          wireframe: true,
          side: THREE.DoubleSide,
        });
        const bufferCylinder = new THREE.Mesh(bufferGeo, bufferMat);
        bufferCylinder.position.copy(mid);
        bufferCylinder.lookAt(endPos);
        bufferCylinder.rotateX(Math.PI / 2); // align with conductor segment
        pylonGroup.add(bufferCylinder);
      }
    });

    // 4. Low-Poly Trees
    const treeGroup = new THREE.Group();
    overlayGroup.add(treeGroup);
    treeGroupRef.current = treeGroup;

    const buildTree = (scale: number): THREE.Group => {
      const tree = new THREE.Group();

      const trunkGeo = new THREE.CylinderGeometry(0.12, 0.2, 1.8, 5);
      const trunkMat = new THREE.MeshStandardMaterial({ color: '#78350f', flatShading: true });
      const trunk = new THREE.Mesh(trunkGeo, trunkMat);
      trunk.position.y = 0.9;
      tree.add(trunk);

      const canopyGeo = new THREE.DodecahedronGeometry(1.2, 0);
      const canopyMat = new THREE.MeshStandardMaterial({ color: '#7cb342', flatShading: true });
      const canopy = new THREE.Mesh(canopyGeo, canopyMat);
      canopy.position.y = 2.3;
      tree.add(canopy);

      tree.scale.set(scale, scale, scale);
      return tree;
    };

    const treePositions = [
      [-15, 12, 1.1],
      [-22, 24, 1.3],
      [18, -14, 1.2],
      [24, -8, 0.9],
      [-5, 20, 1.0],
      [8, 25, 1.3],
    ];

    treePositions.forEach((tp) => {
      const tree = buildTree(tp[2]);
      tree.position.set(tp[0], 0, tp[1]);
      treeGroup.add(tree);
    });

    // 5. Stylized Clouds
    const cloudGroup = new THREE.Group();
    overlayGroup.add(cloudGroup);
    cloudGroupRef.current = cloudGroup;

    const buildCloud = (): THREE.Group => {
      const cloud = new THREE.Group();
      const cloudMat = new THREE.MeshStandardMaterial({
        color: '#ffffff',
        roughness: 0.9,
        flatShading: true,
      });

      const sizes = [1.8, 1.4, 1.5, 1.0];
      const offsets = [
        [0, 0, 0],
        [-1.4, -0.3, 0.1],
        [1.4, -0.1, -0.2],
        [0.6, 0.6, 0.3],
      ];

      sizes.forEach((sz, idx) => {
        const bubble = new THREE.Mesh(new THREE.DodecahedronGeometry(sz, 1), cloudMat);
        const off = offsets[idx];
        bubble.position.set(off[0], off[1], off[2]);
        cloud.add(bubble);
      });

      return cloud;
    };

    const cloudPositions = [
      [-24, 25, -15],
      [8, 28, -22],
      [26, 24, 12],
    ];

    cloudPositions.forEach((cp) => {
      const cloud = buildCloud();
      cloud.position.set(cp[0], cp[1], cp[2]);
      cloudGroup.add(cloud);
    });

    // 6. Agent Swarm satellites and scans
    const satelliteGroup = new THREE.Group();
    overlayGroup.add(satelliteGroup);
    satelliteGroupRef.current = satelliteGroup;

    const buildSatellite = (agentId: string, color: string): THREE.Group => {
      const sat = new THREE.Group();

      // Octahedron Core
      const coreGeo = new THREE.OctahedronGeometry(1.0, 0);
      const coreMat = new THREE.MeshStandardMaterial({
        color: color,
        emissive: color,
        emissiveIntensity: 0.7,
        flatShading: true,
      });
      const core = new THREE.Mesh(coreGeo, coreMat);
      sat.add(core);

      // Torus ring
      const torusGeo = new THREE.TorusGeometry(2.0, 0.08, 6, 24);
      const torusMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.4 });
      const ring = new THREE.Mesh(torusGeo, torusMat);
      ring.rotation.x = Math.PI / 2;
      sat.add(ring);

      // Scanning data cylinder beam
      const beamGeo = new THREE.CylinderGeometry(0.1, 4.5, 45, 16, 1, true);
      const beamMat = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.22,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const beam = new THREE.Mesh(beamGeo, beamMat);
      beam.position.y = -22.5;
      sat.add(beam);

      // Solar panel wings
      const panelGeo = new THREE.BoxGeometry(1.6, 0.1, 0.5);
      const panelMat = new THREE.MeshStandardMaterial({ color: '#334155', metalness: 0.8 });
      
      const panel1 = new THREE.Mesh(panelGeo, panelMat);
      panel1.position.set(-1.8, 0, 0);
      sat.add(panel1);

      const panel2 = new THREE.Mesh(panelGeo, panelMat);
      panel2.position.set(1.8, 0, 0);
      sat.add(panel2);

      satelliteCoresRef.current.push({ mesh: core, agentId });

      return sat;
    };

    // Stagger satellites in altitude orbit
    const s1 = buildSatellite('WEATHER', '#29b6f6');
    s1.position.set(-20, 26, -20);
    satelliteGroup.add(s1);

    const s2 = buildSatellite('IFA', '#f43f5e');
    s2.position.set(20, 26, -20);
    satelliteGroup.add(s2);

    const s3 = buildSatellite('OHL', '#eab308');
    s3.position.set(0, 28, 24);
    satelliteGroup.add(s3);

    // Large main supervisor satellite
    const s4 = buildSatellite('PLANNING', '#00e5ff');
    s4.scale.set(1.5, 1.5, 1.5);
    s4.position.set(0, 32, 0);
    satelliteGroup.add(s4);

    // 7. Electromagnetic exposure field ellipsoids (IFA agent output)
    const hazardFieldGeo = new THREE.SphereGeometry(14, 16, 16);
    const hazardFieldMat = new THREE.MeshBasicMaterial({
      color: '#f43f5e',
      wireframe: true,
      transparent: true,
      opacity: 0.08,
    });
    const hazardField = new THREE.Mesh(hazardFieldGeo, hazardFieldMat);
    hazardField.scale.set(1.3, 0.35, 1.3);
    hazardField.position.set(-15, 2, 10);
    overlayGroup.add(hazardField);

    const hazardCore = new THREE.Mesh(
      new THREE.IcosahedronGeometry(2.5, 1),
      new THREE.MeshBasicMaterial({ color: '#f43f5e', transparent: true, opacity: 0.25 })
    );
    hazardCore.position.set(-15, 2, 10);
    overlayGroup.add(hazardCore);

    // 8. WEATHER PRECIPITATION (Rain particles)
    const rainCount = 6000;
    const rainGeo = new THREE.BufferGeometry();
    const rainCoords = new Float32Array(rainCount * 3);
    const rainVelocities: number[] = [];

    for (let i = 0; i < rainCount * 3; i += 3) {
      rainCoords[i] = (Math.random() - 0.5) * 120;
      rainCoords[i + 1] = Math.random() * 50; // drop elevation height
      rainCoords[i + 2] = (Math.random() - 0.5) * 120;
      rainVelocities.push(0.6 + Math.random() * 0.9);
    }

    rainGeo.setAttribute('position', new THREE.BufferAttribute(rainCoords, 3));
    const rainMat = new THREE.PointsMaterial({
      color: '#38bdf8',
      size: 0.14,
      transparent: true,
      opacity: 0.0, // synchronized to weatherActive state
    });
    const rainSystem = new THREE.Points(rainGeo, rainMat);
    overlayGroup.add(rainSystem);
    rainRef.current = rainSystem;

    // 9. ANIMATION TICK LOOP
    const clock = new THREE.Clock();
    let animFrameId: number;

    const tick = () => {
      const elapsed = clock.getElapsedTime();

      // Satellite hovering
      s1.position.y = 26 + Math.sin(elapsed * 1.4) * 0.9;
      s1.rotation.y = elapsed * 0.3;
      s1.children[3].rotation.z = elapsed * 0.8; // rotate panels

      s2.position.y = 28 + Math.cos(elapsed * 1.6) * 0.8;
      s2.rotation.y = -elapsed * 0.25;
      s2.children[3].rotation.z = -elapsed * 0.6;

      s3.position.y = 24 + Math.sin(elapsed * 1.1) * 1.0;
      s3.rotation.y = elapsed * 0.4;
      s3.children[3].rotation.z = elapsed * 1.1;

      // Pulse coordinator
      s4.position.y = 33 + Math.sin(elapsed * 2.2) * 0.5;
      const supervisorScale = 1.4 + Math.sin(elapsed * 3.5) * 0.06;
      s4.scale.set(supervisorScale, supervisorScale, supervisorScale);

      // Cloud drift wrapping
      cloudGroup.children.forEach((cloud, idx) => {
        cloud.position.x += 0.02 * Math.sin(elapsed * 0.15 + idx);
        if (cloud.position.x > 50) cloud.position.x = -50;
      });

      // Interactive diamond pin rotation
      interactivePinsRef.current.forEach((item, idx) => {
        item.mesh.rotation.y = elapsed * 1.6 + idx;
        const hoverBounce = Math.sin(elapsed * 2.8 + idx) * 0.16;
        item.mesh.position.y = item.annotation.position[1] + hoverBounce;

        // Custom emission intensity on active selection
        if (selectedAnnotation && selectedAnnotation.id === item.annotation.id) {
          item.mesh.scale.set(1.4, 1.4, 1.4);
          (item.mesh.material as THREE.MeshStandardMaterial).emissiveIntensity = 0.6 + Math.sin(elapsed * 9) * 0.4;
        } else {
          item.mesh.scale.set(1.0, 1.0, 1.0);
          (item.mesh.material as THREE.MeshStandardMaterial).emissiveIntensity = 0.5;
        }
      });

      // Risk Prisms Animations (Pulse, Shimmer, and Selection Highlight)
      riskPrismsRef.current.forEach((item) => {
        const mat = item.mesh.material as any;
        
        // 1. Pulse opacity for high-risk immediate/hazard categories
        if (item.category === 'immediate' && mat) {
          mat.opacity = 0.55 + 0.35 * Math.abs(Math.sin(elapsed * Math.PI));
          if (mat.emissiveIntensity !== undefined) {
            mat.emissiveIntensity = 0.4 + 0.5 * Math.abs(Math.sin(elapsed * Math.PI));
          }
        }

        // 2. High-frequency high-fidelity physical jitter/shimmer for low-confidence unconfirmed categories
        if (item.category === 'low_confidence') {
          item.mesh.position.x = Math.sin(elapsed * 55) * 0.08;
          item.mesh.position.z = Math.cos(elapsed * 55) * 0.08;
          item.mesh.scale.set(
            1.0 + Math.sin(elapsed * 40) * 0.03,
            1.0,
            1.0 + Math.cos(elapsed * 40) * 0.03
          );
        }

        // 3. Scale and illuminate on active hover or selection match
        if (selectedAnnotation && selectedAnnotation.id === item.annotationId) {
          if (item.category !== 'low_confidence') {
            item.mesh.scale.set(1.06, 1.06, 1.06);
          }
          if (mat && mat.emissiveIntensity !== undefined && item.category !== 'immediate') {
            mat.emissiveIntensity = 0.8 + 0.25 * Math.sin(elapsed * 9);
          }
        } else {
          if (item.category !== 'low_confidence') {
            item.mesh.scale.set(1.0, 1.0, 1.0);
          }
          if (mat && mat.emissiveIntensity !== undefined && item.category !== 'immediate' && item.category !== 'energy') {
            mat.emissiveIntensity = 0.5;
          }
        }
      });

      // Active precipitation animation
      if (weatherActive && rainRef.current) {
        const posAttr = rainGeo.attributes.position;
        const positions = posAttr.array as Float32Array;

        for (let i = 0; i < rainCount; i++) {
          const yIdx = i * 3 + 1;
          const speed = rainVelocities[i];
          positions[yIdx] -= speed;

          if (positions[yIdx] < 0.1) {
            positions[yIdx] = 48; // recycling
          }
        }
        posAttr.needsUpdate = true;
      }

      // Pulse disc fanning animation during descent scanning phase
      if (mode === 'DESCENT') {
        const scanScale = (resolutionProgress / 100) * 1.5;
        scanDisc.scale.set(scanScale, scanScale, scanScale);
        outerScanRing.scale.set(scanScale, scanScale, scanScale);
        outerScanRingMat.opacity = 0.4 * (1.0 - (resolutionProgress / 100));
      } else {
        scanDisc.scale.set(1, 1, 1);
        outerScanRing.scale.set(1, 1, 1);
        outerScanRingMat.opacity = 0.15;
      }

      // Render Three.js Overlay
      if (renderer && scene && camera) {
        renderer.render(scene, camera);
      }

      animFrameId = requestAnimationFrame(tick);
    };

    tick();

    // Resize handler
    const handleResize = () => {
      if (!containerRef.current || !renderer || !camera) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight || 600;

      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animFrameId);
      renderer.dispose();
    };
  }, [weatherActive]);

  // Synchronize rain particle opacity on toggle
  useEffect(() => {
    if (!rainRef.current) return;
    const material = rainRef.current.material as THREE.PointsMaterial;

    let op = weatherActive ? 0.0 : 0.85;
    const targetOp = weatherActive ? 0.85 : 0.0;

    const interval = setInterval(() => {
      if (Math.abs(op - targetOp) < 0.05) {
        material.opacity = targetOp;
        clearInterval(interval);
      } else {
        op += (targetOp - op) * 0.15;
        material.opacity = op;
      }
    }, 50);

    return () => clearInterval(interval);
  }, [weatherActive]);

  // Sync the interactive diamond annotations pins
  useEffect(() => {
    const overlayGroup = overlayGroupRef.current;
    if (!overlayGroup) return;

    // Clear older pin meshes
    interactivePinsRef.current.forEach((item) => {
      overlayGroup.remove(item.mesh);
    });
    interactivePinsRef.current = [];

    // Create a mesh for each current annotation
    annotations.forEach((anno) => {
      const pinGeo = new THREE.OctahedronGeometry(0.85, 0);
      const pinColor = anno.level === 'hazard' ? '#f43f5e' : anno.level === 'warning' ? '#eab308' : '#00e5ff';
      const pinMat = new THREE.MeshStandardMaterial({
        color: pinColor,
        emissive: pinColor,
        emissiveIntensity: 0.5,
        flatShading: true,
        metalness: 0.1,
        roughness: 0.1,
      });

      const pinMesh = new THREE.Mesh(pinGeo, pinMat);
      pinMesh.position.set(anno.position[0], anno.position[1], anno.position[2]);
      overlayGroup.add(pinMesh);

      interactivePinsRef.current.push({
        mesh: pinMesh,
        annotation: anno,
      });
    });
  }, [annotations]);

  // Synchronize 3D Risk Prisms, Materials, Shadows, and Baseplate Stamp
  useEffect(() => {
    const overlayGroup = overlayGroupRef.current;
    if (!overlayGroup) return;

    // Clear older risk prisms and baseplates
    riskPrismsRef.current.forEach((item) => {
      overlayGroup.remove(item.mesh);
    });
    riskPrismsRef.current = [];

    // Clear older contact shadow meshes if any
    const toRemove = overlayGroup.children.filter(child => child.name === 'risk-prism-shadow' || child.name === 'floating-island-baseplate');
    toRemove.forEach(child => overlayGroup.remove(child));

    if (mode === 'GLOBE') return;

    // 1. Irregular Review Boundary Ground Shadow Baseplate (Grounded stamp shadow)
    const baseplateGeo = new THREE.CylinderGeometry(60, 60, 0.4, 32);
    const baseplateMat = new THREE.MeshBasicMaterial({
      color: '#0f172a',
      transparent: true,
      opacity: 0.35,
    });
    const baseplateMesh = new THREE.Mesh(baseplateGeo, baseplateMat);
    baseplateMesh.position.y = -1.2; // just below the ground surface
    baseplateMesh.name = 'floating-island-baseplate';
    overlayGroup.add(baseplateMesh);

    // 2. Extrude Risk Zones as 3D Prisms and add Soft Contact Footprint Shadows
    riskZones.forEach((zone) => {
      // Create 2D Shape from points
      const shape = new THREE.Shape();
      const pts = zone.points;
      if (pts.length < 3) return;

      shape.moveTo(pts[0][0], pts[0][1]);
      for (let i = 1; i < pts.length; i++) {
        shape.lineTo(pts[i][0], pts[i][1]);
      }
      shape.closePath();

      // Extrude upward (represented as depth along Z in shape space, then rotated)
      const extrudeHeight = zone.score * 40;
      const extrudeSettings = {
        steps: 1,
        depth: extrudeHeight,
        bevelEnabled: false,
      };

      const geo = new THREE.ExtrudeGeometry(shape, extrudeSettings);

      // Materials selection by category
      let mat: THREE.Material;

      if (zone.category === 'flooding') {
        // flooding / water: #3B82F6 MeshPhysicalMaterial translucent
        mat = new THREE.MeshPhysicalMaterial({
          color: '#3B82F6',
          roughness: 0.15,
          metalness: 0.1,
          transmission: 0.4,
          opacity: 0.5,
          transparent: true,
          depthWrite: false,
        });
      } else if (zone.category === 'infrastructure') {
        // infrastructure: #64748B MeshLambertMaterial solid brutalist
        mat = new THREE.MeshLambertMaterial({
          color: '#64748B',
          opacity: 0.7,
          transparent: true,
          flatShading: true,
        });
      } else if (zone.category === 'energy') {
        mat = new THREE.MeshStandardMaterial({
          color: '#A855F7',
          emissive: '#EAB308',
          emissiveIntensity: 0.35,
          transparent: true,
          opacity: 0.65,
          roughness: 0.2,
          metalness: 0.5,
        });
      } else if (zone.category === 'immediate') {
        mat = new THREE.MeshStandardMaterial({
          color: '#EF4444',
          emissive: '#EF4444',
          emissiveIntensity: 0.8,
          transparent: true,
          opacity: 0.8,
          roughness: 0.3,
        });
      } else {
        // low confidence / unverified: #F59E0B basic shimmer material
        mat = new THREE.MeshBasicMaterial({
          color: '#F59E0B',
          transparent: true,
          opacity: 0.75,
        });
      }

      const mesh = new THREE.Mesh(geo, mat);

      // Rotate and position so base sits sit at y = 0
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.y = 0.05; // slightly above terrain base to avoid clipping
      overlayGroup.add(mesh);

      // Attach userData for clicking and identification
      mesh.userData = {
        id: zone.id.toUpperCase(),
        riskCategory: zone.category,
        confidence: zone.confidence,
        source: zone.source,
        score: zone.score,
        title: zone.title,
        description: zone.description,
      };

      riskPrismsRef.current.push({
        mesh,
        annotationId: zone.id.toUpperCase(),
        category: zone.category,
        score: zone.score,
      });

      // 3. Contact shadow: Cast soft planar footprint shadow slightly above ground
      const shadowGeo = new THREE.ShapeGeometry(shape);
      const shadowMat = new THREE.MeshBasicMaterial({
        color: '#0f172a',
        transparent: true,
        opacity: 0.38,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const shadowMesh = new THREE.Mesh(shadowGeo, shadowMat);
      shadowMesh.rotation.x = -Math.PI / 2;
      shadowMesh.position.y = 0.12; // just above ground
      shadowMesh.name = 'risk-prism-shadow';
      overlayGroup.add(shadowMesh);

      // Energy wireframe shell overlay (for category: energy)
      if (zone.category === 'energy') {
        const wireGeo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
        const wireMat = new THREE.MeshBasicMaterial({
          color: '#EAB308',
          wireframe: true,
          transparent: true,
          opacity: 0.75,
        });
        const wireMesh = new THREE.Mesh(wireGeo, wireMat);
        wireMesh.rotation.x = -Math.PI / 2;
        wireMesh.position.y = 0.06;
        wireMesh.name = 'risk-prism-shadow'; // auto-cleanup on redraw
        overlayGroup.add(wireMesh);
      }
    });

  }, [mode, riskZones]);

  // **CRITICAL CAMERA SYNC MATHEMATICAL MANDATE**
  // Execute the per-frame relative ENU pose sync when matrices are updated in Zustand
  useEffect(() => {
    const camera = cameraRef.current;
    if (!camera || !fixedToEnuMatrix || !cesiumCameraMatrix || !cesiumFrustum) return;

    // 1. Sync camera projection parameters from Cesium
    const fovDegrees = cesiumFrustum.fovy * (180.0 / Math.PI);
    if (
      camera.fov !== fovDegrees ||
      camera.aspect !== cesiumFrustum.aspect ||
      camera.near !== cesiumFrustum.near ||
      camera.far !== cesiumFrustum.far
    ) {
      camera.fov = fovDegrees;
      camera.aspect = cesiumFrustum.aspect;
      camera.near = cesiumFrustum.near;
      camera.far = cesiumFrustum.far;
      camera.updateProjectionMatrix();
    }

    // 2. Compute: localCameraMatrix = fixedToEnu * cesiumCameraWorld
    const fixedToEnuMat = new THREE.Matrix4().fromArray(fixedToEnuMatrix);
    const cesiumCameraWorldMat = new THREE.Matrix4().fromArray(cesiumCameraMatrix);

    const localCameraMatrix = new THREE.Matrix4().multiplyMatrices(fixedToEnuMat, cesiumCameraWorldMat);

    // Apply pose parameters directly to lock overlay to world terrain perfectly
    camera.matrix.copy(localCameraMatrix);
    camera.matrixWorld.copy(localCameraMatrix);
    camera.matrixWorldNeedsUpdate = true;
  }, [fixedToEnuMatrix, cesiumCameraMatrix, cesiumFrustum]);

  // Set up global click and mousemove handlers that cleanly toggle pointerEvents
  useEffect(() => {
    const handleGlobalClick = (e: MouseEvent) => {
      const canvas = canvasRef.current;
      const camera = cameraRef.current;
      if (!canvas || !camera) return;

      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX;
      const mouseY = e.clientY;

      // Only handle if clicked inside the canvas bounding box
      if (
        mouseX < rect.left ||
        mouseX > rect.right ||
        mouseY < rect.top ||
        mouseY > rect.bottom
      ) {
        return;
      }

      const mouse = new THREE.Vector2(
        ((mouseX - rect.left) / rect.width) * 2 - 1,
        -((mouseY - rect.top) / rect.height) * 2 + 1
      );

      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(mouse, camera);

      // Raycast pins
      const pinMeshes = interactivePinsRef.current.map((item) => item.mesh);
      if (pinMeshes.length > 0) {
        const intersects = raycaster.intersectObjects(pinMeshes);
        if (intersects.length > 0) {
          const clickedMesh = intersects[0].object as THREE.Mesh;
          const match = interactivePinsRef.current.find((item) => item.mesh === clickedMesh);
          if (match) {
            setSelectedAnnotation(match.annotation);
            e.stopPropagation();
            return;
          }
        }
      }

      // Raycast risk prisms
      const prismMeshes = riskPrismsRef.current.map((item) => item.mesh);
      if (prismMeshes.length > 0) {
        const intersects = raycaster.intersectObjects(prismMeshes);
        if (intersects.length > 0) {
          const clickedMesh = intersects[0].object as THREE.Mesh;
          const match = riskPrismsRef.current.find((item) => item.mesh === clickedMesh);
          if (match) {
            const correspondingAnno = annotations.find((anno) => anno.id === match.annotationId);
            if (correspondingAnno) {
              setSelectedAnnotation(correspondingAnno);
              e.stopPropagation();
              return;
            }
          }
        }
      }

      // Raycast satellites
      const satMeshes = satelliteCoresRef.current.map((item) => item.mesh);
      if (satMeshes.length > 0) {
        const satIntersects = raycaster.intersectObjects(satMeshes);
        if (satIntersects.length > 0) {
          const clickedCore = satIntersects[0].object as THREE.Mesh;
          const match = satelliteCoresRef.current.find((item) => item.mesh === clickedCore);
          if (match) {
            const correspondingAnno = annotations.find((anno) => anno.type === match.agentId);
            if (correspondingAnno) {
              setSelectedAnnotation(correspondingAnno);
              e.stopPropagation();
              return;
            }
          }
        }
      }
    };

    const handleGlobalMouseMove = (e: MouseEvent) => {
      const canvas = canvasRef.current;
      const camera = cameraRef.current;
      if (!canvas || !camera) return;

      // If user is actively dragging (mouse button is down), do not alter pointer events
      if (e.buttons !== 0) return;

      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX;
      const mouseY = e.clientY;

      if (
        mouseX < rect.left ||
        mouseX > rect.right ||
        mouseY < rect.top ||
        mouseY > rect.bottom
      ) {
        return;
      }

      const mouse = new THREE.Vector2(
        ((mouseX - rect.left) / rect.width) * 2 - 1,
        -((mouseY - rect.top) / rect.height) * 2 + 1
      );

      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(mouse, camera);

      // Raycast pins
      const pinMeshes = interactivePinsRef.current.map((item) => item.mesh);
      const pinIntersects = pinMeshes.length > 0 ? raycaster.intersectObjects(pinMeshes) : [];

      // Raycast risk prisms
      const prismMeshes = riskPrismsRef.current.map((item) => item.mesh);
      const prismIntersects = prismMeshes.length > 0 ? raycaster.intersectObjects(prismMeshes) : [];

      // Raycast satellites
      const satMeshes = satelliteCoresRef.current.map((item) => item.mesh);
      const satIntersects = satMeshes.length > 0 ? raycaster.intersectObjects(satMeshes) : [];

      if (pinIntersects.length > 0) {
        canvas.style.pointerEvents = 'auto'; // allow click to register
        canvas.style.cursor = 'pointer';
        const hoveredMesh = pinIntersects[0].object as THREE.Mesh;
        const match = interactivePinsRef.current.find((item) => item.mesh === hoveredMesh);
        if (match) {
          setHoveredObjectName(match.annotation.title);
        }
      } else if (prismIntersects.length > 0) {
        canvas.style.pointerEvents = 'auto'; // allow click to register
        canvas.style.cursor = 'pointer';
        const hoveredMesh = prismIntersects[0].object as THREE.Mesh;
        const match = riskPrismsRef.current.find((item) => item.mesh === hoveredMesh);
        if (match) {
          const correspondingAnno = annotations.find((anno) => anno.id === match.annotationId);
          if (correspondingAnno) {
            setHoveredObjectName(`RISK ZONE: ${correspondingAnno.title}`);
          }
        }
      } else if (satIntersects.length > 0) {
        canvas.style.pointerEvents = 'auto'; // allow click to register
        canvas.style.cursor = 'pointer';
        const hoveredCore = satIntersects[0].object as THREE.Mesh;
        const match = satelliteCoresRef.current.find((item) => item.mesh === hoveredCore);
        if (match) {
          setHoveredObjectName(`${match.agentId} Sub-Agent`);
        }
      } else {
        canvas.style.pointerEvents = 'none'; // pass-through to Cesium underneath
        canvas.style.cursor = 'default';
        setHoveredObjectName(null);
      }
    };

    window.addEventListener('click', handleGlobalClick, true);
    window.addEventListener('mousemove', handleGlobalMouseMove);

    return () => {
      window.removeEventListener('click', handleGlobalClick, true);
      window.removeEventListener('mousemove', handleGlobalMouseMove);
    };
  }, [annotations, riskZones, selectedAnnotation]);

  if (mode === 'GLOBE') {
    return null;
  }

  return (
    <div ref={containerRef} className="absolute inset-0 w-full h-full pointer-events-none select-none z-10">
      
      {/* Transparency top-layer overlay canvas */}
      <canvas
        ref={canvasRef}
        className="w-full h-full block pointer-events-none"
      />

      {/* Hover tooltip HUD */}
      {hoveredObjectName && (
        <div className="absolute top-6 left-1/2 -translate-x-1/2 bg-slate-900/90 text-white font-mono text-[11px] px-3 py-1.5 rounded-md border border-slate-800 shadow-2xl flex items-center gap-2 tracking-wide pointer-events-none">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
          ACTIVE ADVISORY TARGET: <span className="text-cyan-400 font-bold">{hoveredObjectName}</span>
        </div>
      )}

    </div>
  );
};
