import { useEffect, useRef } from "react";
import * as THREE from "three";

function createTerrainTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const context = canvas.getContext("2d");

  const gradient = context.createLinearGradient(0, 0, 512, 512);
  gradient.addColorStop(0, "#edfaff");
  gradient.addColorStop(0.32, "#d7f2e6");
  gradient.addColorStop(0.68, "#f7fbef");
  gradient.addColorStop(1, "#ccecff");
  context.fillStyle = gradient;
  context.fillRect(0, 0, 512, 512);

  context.strokeStyle = "rgba(14, 116, 144, 0.16)";
  context.lineWidth = 2;
  for (let i = 0; i < 10; i += 1) {
    context.beginPath();
    context.ellipse(250, 245, 38 + i * 31, 20 + i * 24, i * 0.18, 0, Math.PI * 2);
    context.stroke();
  }

  context.fillStyle = "rgba(56, 189, 248, 0.22)";
  context.beginPath();
  context.moveTo(0, 314);
  context.bezierCurveTo(92, 250, 186, 354, 300, 290);
  context.bezierCurveTo(406, 230, 456, 292, 512, 236);
  context.lineTo(512, 512);
  context.lineTo(0, 512);
  context.closePath();
  context.fill();

  context.fillStyle = "rgba(59, 130, 246, 0.14)";
  context.beginPath();
  context.ellipse(158, 294, 118, 56, -0.18, 0, Math.PI * 2);
  context.fill();

  context.strokeStyle = "rgba(255, 255, 255, 0.72)";
  context.lineWidth = 3;
  context.beginPath();
  context.moveTo(65, 420);
  context.lineTo(160, 342);
  context.lineTo(260, 295);
  context.lineTo(415, 185);
  context.stroke();

  context.strokeStyle = "rgba(245, 158, 11, 0.78)";
  context.setLineDash([12, 8]);
  context.lineWidth = 4;
  context.beginPath();
  context.moveTo(60, 110);
  context.lineTo(200, 175);
  context.lineTo(355, 128);
  context.lineTo(480, 215);
  context.stroke();
  context.setLineDash([]);

  context.strokeStyle = "rgba(14, 116, 144, 0.16)";
  context.lineWidth = 1;
  for (let i = 0; i <= 512; i += 32) {
    context.beginPath();
    context.moveTo(i, 0);
    context.lineTo(i, 512);
    context.stroke();
    context.beginPath();
    context.moveTo(0, i);
    context.lineTo(512, i);
    context.stroke();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function makeLabel(text, accent = "#0284c7") {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 128;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, 512, 128);
  context.shadowColor = "rgba(15, 23, 42, 0.18)";
  context.shadowBlur = 18;
  context.shadowOffsetY = 8;
  context.fillStyle = "rgba(255, 255, 255, 0.9)";
  context.strokeStyle = "rgba(15, 23, 42, 0.18)";
  context.lineWidth = 2;
  context.roundRect(8, 20, 496, 72, 18);
  context.fill();
  context.stroke();
  context.shadowColor = "transparent";
  context.fillStyle = accent;
  context.fillRect(26, 52, 20, 6);
  context.fillStyle = "#0f172a";
  context.font = "800 29px Inter, Arial, sans-serif";
  context.fillText(text, 58, 66);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(28, 7, 1);
  return sprite;
}

export default function LocalRegionOverlay({ active = true }) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!active || !containerRef.current || !canvasRef.current) return undefined;

    const container = containerRef.current;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 78, 92);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({
      canvas: canvasRef.current,
      antialias: true,
      alpha: true,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);

    const ambient = new THREE.AmbientLight("#ffffff", 1.9);
    scene.add(ambient);

    const sun = new THREE.DirectionalLight("#ffffff", 2.6);
    sun.position.set(30, 80, 45);
    scene.add(sun);

    const model = new THREE.Group();
    model.position.set(0, -7, 0);
    model.rotation.x = -0.03;
    scene.add(model);

    const base = new THREE.Mesh(
      new THREE.CylinderGeometry(51, 54, 3.4, 9),
      new THREE.MeshStandardMaterial({
        color: "#f8fafc",
        roughness: 0.52,
        metalness: 0.02,
      }),
    );
    base.scale.set(1.04, 1, 0.68);
    base.rotation.y = Math.PI / 9;
    base.position.y = -2.6;
    model.add(base);

    const baseShadow = new THREE.Mesh(
      new THREE.CylinderGeometry(54, 58, 0.22, 9),
      new THREE.MeshBasicMaterial({ color: "#0f172a", transparent: true, opacity: 0.16 }),
    );
    baseShadow.scale.set(1.08, 1, 0.72);
    baseShadow.rotation.y = Math.PI / 9;
    baseShadow.position.set(2, -4.6, 4);
    model.add(baseShadow);

    const terrain = new THREE.Mesh(
      new THREE.CircleGeometry(45, 96),
      new THREE.MeshStandardMaterial({
        map: createTerrainTexture(),
        roughness: 0.86,
        metalness: 0.04,
        transparent: true,
        opacity: 0.96,
        side: THREE.DoubleSide,
      }),
    );
    terrain.rotation.x = -Math.PI / 2;
    terrain.scale.set(1.08, 0.73, 1);
    terrain.position.y = 0.2;

    const positions = terrain.geometry.attributes.position;
    for (let i = 0; i < positions.count; i += 1) {
      const x = positions.getX(i);
      const y = positions.getY(i);
      const angle = Math.atan2(y, x);
      const radius = Math.hypot(x, y);
      const irregularEdge = 1 + Math.sin(angle * 3.2) * 0.08 + Math.cos(angle * 5.1) * 0.06;
      if (radius > 34) {
        const edgePull = Math.min(1, (radius - 34) / 11);
        positions.setX(i, x * (1 - edgePull * (1 - irregularEdge)));
        positions.setY(i, y * (1 - edgePull * (1 - irregularEdge)));
      }
      const height =
        Math.sin(x * 0.18) * 2.6 +
        Math.cos(y * 0.22) * 2.2 +
        Math.max(0, 8 - Math.hypot(x + 12, y - 10) * 0.18) -
        Math.max(0, radius - 35) * 0.12;
      positions.setZ(i, height);
    }
    positions.needsUpdate = true;
    terrain.geometry.computeVertexNormals();
    model.add(terrain);

    const boundaryCurve = new THREE.EllipseCurve(0, 0, 42, 28, 0, Math.PI * 2);
    const boundaryPoints = boundaryCurve.getPoints(96).map((point, index) => {
      const wave = 1 + Math.sin(index * 0.38) * 0.035 + Math.cos(index * 0.21) * 0.025;
      return new THREE.Vector3(point.x * wave, 5.2, point.y * wave);
    });
    const boundary = new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(boundaryPoints),
      new THREE.LineBasicMaterial({ color: "#0ea5e9", transparent: true, opacity: 0.92 }),
    );
    model.add(boundary);

    const reviewWash = new THREE.Mesh(
      new THREE.CircleGeometry(41, 96),
      new THREE.MeshBasicMaterial({ color: "#67e8f9", transparent: true, opacity: 0.12, side: THREE.DoubleSide }),
    );
    reviewWash.rotation.x = -Math.PI / 2;
    reviewWash.scale.set(1.05, 0.66, 1);
    reviewWash.position.y = 5.05;
    model.add(reviewWash);

    const water = new THREE.Mesh(
      new THREE.CylinderGeometry(11, 14, 5.6, 40),
      new THREE.MeshPhysicalMaterial({
        color: "#38bdf8",
        transparent: true,
        opacity: 0.34,
        roughness: 0.08,
        transmission: 0.2,
        depthWrite: false,
      }),
    );
    water.scale.set(1.8, 1, 0.72);
    water.position.set(-24, 7.8, 8);
    model.add(water);

    const floodWash = new THREE.Mesh(
      new THREE.CircleGeometry(18, 48),
      new THREE.MeshBasicMaterial({ color: "#60a5fa", transparent: true, opacity: 0.2, side: THREE.DoubleSide }),
    );
    floodWash.rotation.x = -Math.PI / 2;
    floodWash.scale.set(1.8, 0.78, 1);
    floodWash.position.set(-20, 5.15, 6);
    model.add(floodWash);

    const utilityMat = new THREE.MeshStandardMaterial({
      color: "#f59e0b",
      emissive: "#f59e0b",
      emissiveIntensity: 0.45,
      roughness: 0.3,
    });
    [-24, 0, 24].forEach((x) => {
      const pylon = new THREE.Mesh(new THREE.ConeGeometry(1.5, 17, 4), utilityMat);
      pylon.position.set(x, 10, -13);
      model.add(pylon);
    });
    const cable = new THREE.Mesh(
      new THREE.BoxGeometry(58, 0.45, 0.45),
      new THREE.MeshBasicMaterial({ color: "#f59e0b" }),
    );
    cable.position.set(0, 18, -13);
    model.add(cable);

    const access = new THREE.Mesh(
      new THREE.BoxGeometry(62, 0.42, 2.2),
      new THREE.MeshBasicMaterial({ color: "#22c55e", transparent: true, opacity: 0.82 }),
    );
    access.position.set(4, 5.1, 18);
    access.rotation.y = -0.55;
    model.add(access);

    const lowConfidenceMat = new THREE.MeshStandardMaterial({
      color: "#f59e0b",
      emissive: "#f59e0b",
      emissiveIntensity: 0.38,
      transparent: true,
      opacity: 0.7,
      roughness: 0.36,
    });
    const immediateMat = new THREE.MeshStandardMaterial({
      color: "#ef4444",
      emissive: "#ef4444",
      emissiveIntensity: 0.55,
      transparent: true,
      opacity: 0.78,
    });
    const fallbackMat = new THREE.MeshBasicMaterial({
      color: "#a78bfa",
      transparent: true,
      opacity: 0.3,
      wireframe: true,
    });
    [
      [-8, 9, -4, 7, lowConfidenceMat],
      [16, 9, 7, 10, immediateMat],
      [29, 9, -18, 6, lowConfidenceMat],
    ].forEach(([x, y, z, height, material]) => {
      const prism = new THREE.Mesh(new THREE.CylinderGeometry(2.8, 3.7, height, 4), material);
      prism.position.set(x, y + height / 2, z);
      prism.rotation.y = Math.PI / 4;
      model.add(prism);

      const pin = new THREE.Mesh(new THREE.OctahedronGeometry(2, 0), material);
      pin.position.set(x, y + height + 3, z);
      model.add(pin);
    });

    const fallbackZone = new THREE.Mesh(new THREE.IcosahedronGeometry(8, 1), fallbackMat);
    fallbackZone.scale.set(1.4, 0.42, 0.8);
    fallbackZone.position.set(24, 10, -2);
    model.add(fallbackZone);

    const rainMat = new THREE.MeshBasicMaterial({ color: "#38bdf8", transparent: true, opacity: 0.34 });
    [
      [-30, 10, 4, 18],
      [-22, 10, 12, 27],
      [-14, 10, 2, 22],
      [-4, 10, 14, 15],
    ].forEach(([x, y, z, h]) => {
      const column = new THREE.Mesh(new THREE.CylinderGeometry(1.6, 1.6, h, 16), rainMat);
      column.position.set(x, y + h / 2, z);
      model.add(column);
    });

    const windMat = new THREE.MeshBasicMaterial({ color: "#2563eb", transparent: true, opacity: 0.78 });
    [-14, 2, 18].forEach((x) => {
      const arrow = new THREE.ArrowHelper(
        new THREE.Vector3(1, 0, -0.35).normalize(),
        new THREE.Vector3(x, 25, 28),
        16,
        "#2563eb",
        4.5,
        2.5,
      );
      arrow.line.material = windMat;
      model.add(arrow);
    });

    const labels = [
      ["Water / flood", -31, 16, 1, "#0284c7"],
      ["Rain", -23, 39, 11, "#2563eb"],
      ["Wind", 12, 38, 28, "#2563eb"],
      ["Utilities", 23, 29, -14, "#f59e0b"],
      ["Access", 17, 16, 20, "#16a34a"],
      ["Review boundary", -12, 26, -24, "#0891b2"],
    ];
    labels.forEach(([text, x, y, z, accent]) => {
      const label = makeLabel(text, accent);
      label.position.set(x, y, z);
      model.add(label);
    });

    let animationId;
    const animate = () => {
      const elapsed = Date.now() * 0.001;
      model.rotation.y = Math.sin(elapsed * 0.25) * 0.06;
      water.material.opacity = 0.3 + Math.sin(elapsed * 1.7) * 0.04;
      fallbackZone.rotation.y += 0.01;
      renderer.render(scene, camera);
      animationId = requestAnimationFrame(animate);
    };
    animate();

    const handleResize = () => {
      if (!container.clientWidth || !container.clientHeight) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animationId);
      renderer.dispose();
      terrain.geometry.dispose();
      base.geometry.dispose();
    };
  }, [active]);

  if (!active) return null;

  return (
    <div className="local-region-overlay" ref={containerRef} aria-hidden="true">
      <canvas ref={canvasRef} />
      <div className="local-region-badge">
        Cesium globe + local risk model
        <span>Agent layers visualised for human review</span>
      </div>
    </div>
  );
}
