import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Button, Descriptions, Popover, Segmented, Space, Tag } from 'antd';
import {
  AimOutlined,
  AppstoreOutlined,
  BorderOuterOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import request from '../api/request';
import '../styles/mine-overview.css';

const VIEW_PRESETS = {
  global: { position: [28, 17, 32], target: [1, -3, -4.5] },
  surface: { position: [24, 14, 25], target: [0, 1, -4.5] },
  underground: { position: [23, -1, 25], target: [6, -9, -4.5] },
  drainage: { position: [26, -1.5, 11], target: [13.2, -4.8, -4.5] },
};

function statusColor(status) {
  if (status === 'normal') return 'green';
  if (status === 'research') return 'blue';
  return 'orange';
}

function createLabel(text, className = '') {
  const el = document.createElement('div');
  el.className = `mine-label ${className}`;
  el.textContent = text;
  return new CSS2DObject(el);
}

function createBuilding({ name, x, z, w = 3.2, h = 2.6, d = 3, color = 0x526271, roof = 0x26384a, facilityId }) {
  const group = new THREE.Group();
  group.userData.facilityId = facilityId;

  const wall = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    new THREE.MeshStandardMaterial({ color, roughness: 0.55, metalness: 0.18 }),
  );
  wall.position.y = h / 2;
  wall.castShadow = true;
  wall.receiveShadow = true;
  wall.userData.facilityId = facilityId;
  group.add(wall);

  const top = new THREE.Mesh(
    new THREE.ConeGeometry(Math.max(w, d) * 0.72, 0.85, 4),
    new THREE.MeshStandardMaterial({ color: roof, roughness: 0.6, metalness: 0.22 }),
  );
  top.rotation.y = Math.PI / 4;
  top.position.y = h + 0.42;
  top.userData.facilityId = facilityId;
  group.add(top);

  const win = new THREE.Mesh(
    new THREE.PlaneGeometry(w * 0.34, h * 0.24),
    new THREE.MeshBasicMaterial({ color: 0xffdfa2 }),
  );
  win.position.set(0, h * 0.58, d / 2 + 0.01);
  group.add(win);

  const label = createLabel(name);
  label.position.set(0, h + 1.2, 0);
  group.add(label);
  group.position.set(x, 0, z);
  return group;
}

function createHeadframe(x, z, height, scale, facilityId) {
  const group = new THREE.Group();
  group.userData.facilityId = facilityId;
  const steel = new THREE.MeshStandardMaterial({ color: 0x6e8192, roughness: 0.3, metalness: 0.72 });
  const base = 0.85 * scale;
  [[-base, -base], [base, -base], [-base, base], [base, base]].forEach(([dx, dz]) => {
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.12 * scale, 0.12 * scale, height, 8), steel);
    pole.position.set(dx, height / 2, dz);
    pole.userData.facilityId = facilityId;
    group.add(pole);
  });
  const platform = new THREE.Mesh(new THREE.BoxGeometry(base * 2.6, 0.28, base * 2.6), steel);
  platform.position.y = height;
  group.add(platform);
  [-1, 1].forEach((s) => {
    const wheel = new THREE.Mesh(
      new THREE.TorusGeometry(0.48 * scale, 0.09 * scale, 8, 18),
      new THREE.MeshStandardMaterial({ color: 0x8797a5, roughness: 0.22, metalness: 0.86 }),
    );
    wheel.position.set(s * 0.68 * scale, height + 0.35, 0);
    group.add(wheel);
  });
  group.position.set(x, 0, z);
  return group;
}

function createPipeBetween(start, end, radius, material, facilityId) {
  const from = new THREE.Vector3(...start);
  const to = new THREE.Vector3(...end);
  const direction = new THREE.Vector3().subVectors(to, from);
  const length = direction.length();
  const mesh = new THREE.Mesh(
    new THREE.CylinderGeometry(radius, radius, length, 14),
    material,
  );
  mesh.position.copy(from).add(to).multiplyScalar(0.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.clone().normalize());
  mesh.userData.facilityId = facilityId;
  return mesh;
}

function buildFiveWellResearchZone(drainage) {
  const envelope = new THREE.Group();
  const infrastructure = new THREE.Group();
  const facilityId = 'five_well_zone';

  // 全局视图中用于定位试验区的半透明边界。进入“五钻孔区”后会隐藏。
  const envelopeMesh = new THREE.Mesh(
    new THREE.BoxGeometry(8.2, 2.15, 5.0),
    new THREE.MeshStandardMaterial({
      color: 0x8a939a,
      transparent: true,
      opacity: 0.11,
      roughness: 0.55,
      side: THREE.DoubleSide,
    }),
  );
  envelopeMesh.position.set(13.1, -9.05, -4.5);
  envelopeMesh.userData.facilityId = facilityId;
  envelope.add(envelopeMesh);

  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(8.2, 2.15, 5.0)),
    new THREE.LineBasicMaterial({ color: 0x359fda, transparent: true, opacity: 0.5 }),
  );
  edges.position.copy(envelopeMesh.position);
  edges.userData.facilityId = facilityId;
  envelope.add(edges);

  const boreholeMat = new THREE.MeshStandardMaterial({ color: 0x086fd6, roughness: 0.24, metalness: 0.48 });
  const manifoldMat = new THREE.MeshStandardMaterial({ color: 0x14a7dd, roughness: 0.28, metalness: 0.5 });
  const riserMat = new THREE.MeshStandardMaterial({ color: 0x0b5f9f, roughness: 0.3, metalness: 0.62 });

  // 五条水平钻孔：相对于 V11 在水平面整体旋转 90°，沿 X 方向展开。
  // 五孔在 Z 方向等间距排布，中心孔对应 z=-4.5。
  const boreholeLength = 6.8;
  const rightEndX = 13.1 + boreholeLength / 2;
  const wellZs = [-5.9, -5.2, -4.5, -3.8, -3.1];
  wellZs.forEach((z, index) => {
    const well = new THREE.Mesh(
      new THREE.CylinderGeometry(0.09, 0.09, boreholeLength, 14),
      boreholeMat,
    );
    well.rotation.z = Math.PI / 2; // Cylinder 默认沿 Y；旋转后沿 X。
    well.position.set(13.1, -8.9, z);
    well.userData.facilityId = facilityId;
    infrastructure.add(well);

    const wellLabel = createLabel(`W${index + 1}`, 'mine-label-well');
    wellLabel.position.set(9.55, -8.55, z);
    infrastructure.add(wellLabel);
  });

  // 五孔末端汇入同一根水平汇管，再连接到垂直抽采立管。
  const manifold = new THREE.Mesh(
    new THREE.CylinderGeometry(0.12, 0.12, 3.3, 14),
    manifoldMat,
  );
  manifold.rotation.x = Math.PI / 2; // 沿 Z 方向。
  manifold.position.set(rightEndX, -8.9, -4.5);
  manifold.userData.facilityId = facilityId;
  infrastructure.add(manifold);

  // 垂直抽采立管：从井下汇管一直连接到地表井口。
  const riserBottomY = -8.9;
  const riserTopY = 0.5;
  const riser = createPipeBetween(
    [rightEndX, riserBottomY, -4.5],
    [rightEndX, riserTopY, -4.5],
    0.16,
    riserMat,
    facilityId,
  );
  infrastructure.add(riser);

  // 地表井口/法兰，用于明确“地下水平钻孔—垂直井口”的空间关系。
  const collar = new THREE.Mesh(
    new THREE.TorusGeometry(0.34, 0.08, 10, 22),
    new THREE.MeshStandardMaterial({ color: 0x3f7fa8, roughness: 0.25, metalness: 0.72 }),
  );
  collar.rotation.x = Math.PI / 2;
  collar.position.set(rightEndX, 0.53, -4.5);
  collar.userData.facilityId = facilityId;
  infrastructure.add(collar);

  const cap = new THREE.Mesh(
    new THREE.CylinderGeometry(0.23, 0.23, 0.7, 14),
    riserMat,
  );
  cap.position.set(rightEndX, 0.82, -4.5);
  cap.userData.facilityId = facilityId;
  infrastructure.add(cap);

  const riserLabel = createLabel('五钻孔汇流立管 / 地表井口', 'mine-label-research');
  riserLabel.position.set(rightEndX, 2.0, -4.5);
  infrastructure.add(riserLabel);

  const testLabel = createLabel('五钻孔煤系气抽采试验区', 'mine-label-research');
  testLabel.position.set(13.1, -6.9, -4.5);
  infrastructure.add(testLabel);

  drainage.add(envelope, infrastructure);
  return { envelope, infrastructure, rightEndX };
}

function buildMineScene(scene) {
  const root = new THREE.Group();
  const surface = new THREE.Group();
  const underground = new THREE.Group();
  const ground = new THREE.Group();
  const drainage = new THREE.Group();

  root.add(ground, surface, underground, drainage);
  scene.add(root);

  // 白色背景下采用更浅的地表颜色，提高井下对象的可辨识度。
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x263746,
    roughness: 0.94,
    transparent: true,
    opacity: 0.92,
    side: THREE.DoubleSide,
  });
  const groundPlane = new THREE.Mesh(new THREE.PlaneGeometry(58, 38), groundMat);
  groundPlane.rotation.x = -Math.PI / 2;
  groundPlane.position.set(0, 0, -4.5);
  groundPlane.receiveShadow = true;
  ground.add(groundPlane);

  const grid = new THREE.PolarGridHelper(21, 48, 24, 192, 0x267b9e, 0x24445a);
  grid.position.y = 0.03;
  ground.add(grid);

  const layers = [
    { y: -1.5, h: 3, c: 0x59656b },
    { y: -4.25, h: 2.5, c: 0x4e5b62 },
    { y: -6.55, h: 2.1, c: 0x3f4e57 },
    { y: -8.9, h: 2.6, c: 0x20272d },
    { y: -11.4, h: 2.4, c: 0x465158 },
  ];
  layers.forEach((item) => {
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(3.2, item.h, 7),
      new THREE.MeshStandardMaterial({ color: item.c, roughness: 0.84 }),
    );
    mesh.position.set(-14, item.y, -4.5);
    underground.add(mesh);
  });

  const coalSeam = new THREE.Mesh(
    new THREE.BoxGeometry(31, 3, 6.5),
    new THREE.MeshStandardMaterial({ color: 0x17191c, roughness: 0.48, metalness: 0.12 }),
  );
  coalSeam.position.set(2, -9.5, -4.5);
  underground.add(coalSeam);
  const seamLabel = createLabel('煤层 / 抽采目标层', 'mine-label-strong');
  seamLabel.position.set(-9, -7.2, -4.5);
  underground.add(seamLabel);

  const shaftMat = new THREE.MeshStandardMaterial({ color: 0x4e6171, roughness: 0.35, metalness: 0.7 });
  const shafts = [
    { id: 'main_shaft', name: '主井', x: 0, r: 0.68 },
    { id: 'aux_shaft', name: '副井', x: 4, r: 0.56 },
    { id: 'vent_shaft', name: '回风井', x: -7, r: 0.44 },
  ];
  shafts.forEach((s) => {
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(s.r, s.r, 10.8, 18), shaftMat);
    shaft.position.set(s.x, -5.4, -4.5);
    shaft.userData.facilityId = s.id;
    underground.add(shaft);

    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(s.r + 0.15, 0.08, 8, 18),
      new THREE.MeshStandardMaterial({ color: 0x8093a3, metalness: 0.8, roughness: 0.25 }),
    );
    ring.rotation.x = Math.PI / 2;
    ring.position.set(s.x, 0.05, -4.5);
    ring.userData.facilityId = s.id;
    surface.add(ring);
  });
  surface.add(createHeadframe(0, -4.5, 8.2, 1, 'main_shaft'));
  surface.add(createHeadframe(4, -4.5, 6.3, 0.78, 'aux_shaft'));

  const roadwayMat = new THREE.MeshStandardMaterial({ color: 0x59534e, roughness: 0.83, metalness: 0.05 });
  [-5.8, -4.5, -3.2].forEach((z, idx) => {
    const road = new THREE.Mesh(new THREE.BoxGeometry(15, 2.25, 1.15), roadwayMat);
    road.position.set(7, -8.8, z);
    road.userData.facilityId = 'roadway';
    underground.add(road);
    const names = ['运输巷', '轨道/进风巷', '回风巷'];
    const label = createLabel(names[idx]);
    label.position.set(7, -7.25, z);
    underground.add(label);
  });

  const fiveWell = buildFiveWellResearchZone(drainage);

  surface.add(createBuilding({ name: '煤系气抽采站', x: 9, z: 4, w: 5.3, h: 3.2, d: 3.2, color: 0x536a75, facilityId: 'drainage_station' }));
  surface.add(createBuilding({ name: '智能监测中心', x: 10, z: -1, w: 4.5, h: 2.8, d: 3.0, color: 0x566878, facilityId: 'monitor_center' }));
  surface.add(createBuilding({ name: '变配电站', x: 6, z: 6, w: 3.2, h: 2.2, d: 2.6, color: 0x4c646e, facilityId: 'power_station' }));
  surface.add(createBuilding({ name: '提升机房', x: 3.6, z: -1.8, w: 3.3, h: 2.5, d: 3.0, color: 0x5d6d75, facilityId: 'main_shaft' }));
  surface.add(createBuilding({ name: '综合实验楼', x: -7.2, z: 2.5, w: 4.7, h: 3.0, d: 3.4, color: 0x5b6c78, facilityId: 'monitor_center' }));

  const tankMat = new THREE.MeshStandardMaterial({ color: 0x8496a5, roughness: 0.3, metalness: 0.72 });
  [7.2, 8.1, 9.0].forEach((x) => {
    const tank = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 3.6, 16), tankMat);
    tank.position.set(x, 1.8, 6.2);
    tank.userData.facilityId = 'drainage_station';
    surface.add(tank);
    const cap = new THREE.Mesh(new THREE.SphereGeometry(0.34, 12, 8), tankMat);
    cap.scale.y = 0.45;
    cap.position.set(x, 3.6, 6.2);
    surface.add(cap);
  });
  const manifold = new THREE.Mesh(
    new THREE.CylinderGeometry(0.10, 0.10, 4.2, 10),
    new THREE.MeshStandardMaterial({ color: 0x2f8bd8, roughness: 0.3, metalness: 0.55 }),
  );
  manifold.rotation.z = Math.PI / 2;
  manifold.position.set(8.1, 0.8, 5.2);
  surface.add(manifold);

  const fan = new THREE.Mesh(
    new THREE.CylinderGeometry(0.68, 0.9, 1.5, 10),
    new THREE.MeshStandardMaterial({ color: 0x566978, roughness: 0.45, metalness: 0.45 }),
  );
  fan.position.set(-7, 0.75, -4.5);
  fan.userData.facilityId = 'vent_shaft';
  surface.add(fan);
  const fanLabel = createLabel('回风井 / 通风机');
  fanLabel.position.set(-7, 3.3, -4.5);
  surface.add(fanLabel);

  const road = new THREE.Mesh(
    new THREE.PlaneGeometry(2.0, 22),
    new THREE.MeshStandardMaterial({ color: 0x626a70, roughness: 0.95 }),
  );
  road.rotation.x = -Math.PI / 2;
  road.position.set(1.8, 0.035, 3.5);
  surface.add(road);

  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x684a28, roughness: 0.9 });
  const leafMat = new THREE.MeshStandardMaterial({ color: 0x3d7d4c, roughness: 0.75 });
  const treePositions = [[-17,-8],[-15,-5],[-16,0],[-14,5],[-12,8],[-10,9],[-18,4],[-11,-9]];
  treePositions.forEach(([x, z]) => {
    const tree = new THREE.Group();
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.10, 0.14, 1.0, 6), trunkMat);
    trunk.position.y = 0.5;
    tree.add(trunk);
    const leaves = new THREE.Mesh(new THREE.ConeGeometry(0.55, 1.7, 7), leafMat);
    leaves.position.y = 1.55;
    tree.add(leaves);
    tree.position.set(x, 0, z);
    surface.add(tree);
  });

  return {
    root,
    surface,
    underground,
    ground,
    drainage,
    groundPlane,
    coalSeam,
    drainageEnvelope: fiveWell.envelope,
    drainageInfrastructure: fiveWell.infrastructure,
  };
}

export default function MineOverview({ onOpenPrediction, onOpenSimulation }) {
  const containerRef = useRef(null);
  const sceneApiRef = useRef(null);
  const [overview, setOverview] = useState(null);
  const [selectedFacility, setSelectedFacility] = useState(null);
  const [viewMode, setViewMode] = useState('global');
  const [autoRotate, setAutoRotate] = useState(false);

  useEffect(() => {
    let timer;
    const load = () => {
      request.get('/mine/overview')
        .then((res) => {
          setOverview(res.data);
          if (res.data.facilities?.length) setSelectedFacility((prev) => prev || res.data.facilities[0]);
        })
        .catch(() => {});
    };
    load();
    timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
  }, []);

  const setPreset = (mode) => {
    setViewMode(mode);
    const api = sceneApiRef.current;
    if (!api) return;
    const preset = VIEW_PRESETS[mode] || VIEW_PRESETS.global;
    api.camera.position.set(...preset.position);
    api.controls.target.set(...preset.target);
    api.controls.update();

    const {
      surface,
      underground,
      ground,
      drainage,
      groundPlane,
      coalSeam,
      drainageEnvelope,
      drainageInfrastructure,
    } = api.groups;

    surface.visible = true;
    underground.visible = true;
    drainage.visible = true;
    ground.visible = true;
    drainageEnvelope.visible = true;
    drainageInfrastructure.visible = true;
    coalSeam.visible = true;
    groundPlane.material.opacity = 0.92;

    if (mode === 'surface') {
      underground.visible = false;
      drainage.visible = false;
      groundPlane.material.opacity = 1;
    } else if (mode === 'underground') {
      surface.visible = false;
      groundPlane.material.opacity = 0.18;
    } else if (mode === 'drainage') {
      // 五钻孔科研聚焦模式：保留矿井全局场景，仅隐去红框对应的
      // “煤层 / 抽采目标层”实体外壁，让钻孔、汇管和垂直立管能够透视显示。
      // 地面设施、井筒、三条巷道、地层柱、地表和五钻孔标识全部保留。
      surface.visible = true;
      underground.visible = true;
      ground.visible = true;
      drainage.visible = true;
      drainageEnvelope.visible = true;
      drainageInfrastructure.visible = true;
      coalSeam.visible = false;
      groundPlane.material.opacity = 0.92;
    }
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;
    container.innerHTML = '';

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x101d2b);
    scene.fog = new THREE.FogExp2(0x101d2b, 0.0034);

    const camera = new THREE.PerspectiveCamera(45, 1, 0.3, 180);
    const preset = VIEW_PRESETS.global;
    camera.position.set(...preset.position);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);

    const labelRenderer = new CSS2DRenderer();
    labelRenderer.domElement.className = 'mine-label-layer';
    container.appendChild(labelRenderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(...preset.target);
    controls.enableDamping = true;
    controls.dampingFactor = 0.075;
    controls.minDistance = 7;
    controls.maxDistance = 75;
    controls.maxPolarAngle = Math.PI * 0.9;
    controls.autoRotate = false;
    controls.autoRotateSpeed = 0.22;

    scene.add(new THREE.AmbientLight(0xd7e9fa, 1.15));
    scene.add(new THREE.HemisphereLight(0xa4d3f0, 0x27394a, 1.1));
    const sun = new THREE.DirectionalLight(0xe5f2ff, 2.2);
    sun.position.set(28, 30, 15);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    scene.add(sun);
    const fill = new THREE.DirectionalLight(0x51c7ef, 0.8);
    fill.position.set(-18, 8, -12);
    scene.add(fill);

    const groups = buildMineScene(scene);
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    const resize = () => {
      const w = Math.max(container.clientWidth, 300);
      const h = Math.max(container.clientHeight, 1);
      camera.aspect = w / h;
      camera.zoom = Math.min(1, camera.aspect / 1.4);
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);
      labelRenderer.setSize(w, h);
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    resize();

    const onPointerDown = (event) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(scene.children, true);
      for (const hit of hits) {
        let obj = hit.object;
        while (obj) {
          if (obj.userData?.facilityId) {
            const id = obj.userData.facilityId;
            request.get(`/mine/facilities/${id}`).then((res) => setSelectedFacility(res.data)).catch(() => {});

            // 点击五钻孔科研区即进入隔离细节模式。
            if (id === 'five_well_zone') setPreset('drainage');
            return;
          }
          obj = obj.parent;
        }
      }
    };
    renderer.domElement.addEventListener('pointerdown', onPointerDown);

    let frameId;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
      labelRenderer.render(scene, camera);
    };
    animate();

    sceneApiRef.current = { scene, camera, renderer, labelRenderer, controls, groups };

    return () => {
      cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener('pointerdown', onPointerDown);
      controls.dispose();
      renderer.dispose();
      container.innerHTML = '';
      sceneApiRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (sceneApiRef.current?.controls) sceneApiRef.current.controls.autoRotate = autoRotate;
  }, [autoRotate]);

  const summary = overview?.summary || {};
  const realtime = overview?.realtime || {};
  const facility = selectedFacility;

  const statItems = useMemo(() => ([
    ['地面设施', summary.surfaceFacilities ?? '--'],
    ['井下系统', summary.undergroundSystems ?? '--'],
    ['抽采钻孔', summary.activeDrainageWells ?? '--'],
    ['当前告警', summary.alarms ?? '--'],
  ]), [summary]);

  return (
    <div className="mine-overview-page">
      <div className="mine-overview-header">
        <div>
          <h1>煤系气矿井全局数字孪生</h1>
          <p>地面设施—井筒—煤层—巷道—水平钻孔—汇管—垂直抽采井口一体化空间映射</p>
        </div>
        <div className="mine-overview-header-status">
          <span className="online-dot" /> 仿真数据流 · 每 5 秒刷新
        </div>
      </div>

      <div className="mine-overview-shell">
        <div className="mine-scene-card">
          <div className="mine-scene-toolbar">
            <Segmented
              value={viewMode}
              onChange={setPreset}
              options={[
                { label: '全局', value: 'global', icon: <AppstoreOutlined /> },
                { label: '地面', value: 'surface', icon: <BorderOuterOutlined /> },
                { label: '井下', value: 'underground', icon: <AimOutlined /> },
                { label: '五钻孔区', value: 'drainage', icon: <AimOutlined /> },
              ]}
            />
            <Space size={6}>
              <Button size="small" onClick={() => setAutoRotate((v) => !v)}>{autoRotate ? '停止自转' : '自动旋转'}</Button>
              <Button size="small" icon={<ReloadOutlined />} onClick={() => setPreset('global')}>恢复全局</Button>
            </Space>
          </div>

          <div ref={containerRef} className="mine-three-container" />

          <div className="mine-scene-badge">数字孪生 · 全矿井空间场景</div>
          <div className="mine-interaction-tip">
            {viewMode === 'drainage'
              ? '五钻孔透视聚焦：仅隐藏目标煤层外壁，其余矿井对象保持可见'
              : '左键旋转 · 滚轮缩放 · 右键平移 · 点击五钻孔区进入透视聚焦视图'}
          </div>

          <div className="mine-status-strip">
            {statItems.map(([label, value]) => (
              <div key={label} className="mine-status-item">
                <span>{label}</span><b>{value}</b>
              </div>
            ))}
          </div>
        </div>

        <aside className="mine-overview-side">
          <section className="mine-hud-panel">
            <div className="mine-hud-title">抽采实时状态</div>
            <div className="mine-realtime-grid">
              <div><span>抽采负压</span><b>{realtime.negativePressureKPa ?? '--'} kPa</b></div>
              <div><span>甲烷浓度</span><b>{realtime.methaneConcentrationPct ?? '--'} %</b></div>
              <div><span>混合流量</span><b>{realtime.mixedFlowM3Min ?? '--'} m³/min</b></div>
              <div><span>回风瓦斯</span><b>{realtime.returnAirMethanePct ?? '--'} %</b></div>
            </div>
          </section>

          <section className="mine-hud-panel mine-facility-panel">
            <div className="mine-hud-title">设施 / 科研对象信息</div>
            {facility ? (
              <>
                <div className="facility-name-row">
                  <strong>{facility.name}</strong>
                  <Tag color={statusColor(facility.status)}>{facility.status === 'research' ? '科研对象' : '正常'}</Tag>
                </div>
                <p className="facility-desc">{facility.description}</p>
                <Descriptions size="small" column={1} colon={false} className="mine-descriptions">
                  <Descriptions.Item label="类别">{facility.category}</Descriptions.Item>
                  <Descriptions.Item label="空间坐标">
                    ({facility.position?.x}, {facility.position?.y}, {facility.position?.z})
                  </Descriptions.Item>
                  {facility.engineering?.boreholeOrientation && (
                    <Descriptions.Item label="钻孔方向">{facility.engineering.boreholeOrientation}</Descriptions.Item>
                  )}
                  {facility.engineering?.spacing && (
                    <Descriptions.Item label="孔间距">{facility.engineering.spacing}</Descriptions.Item>
                  )}
                  {facility.engineering?.connection && (
                    <Descriptions.Item label="抽采连接">{facility.engineering.connection}</Descriptions.Item>
                  )}
                  <Descriptions.Item label="数据来源">FastAPI / Digital Twin Backend</Descriptions.Item>
                </Descriptions>
              </>
            ) : <div className="mine-empty-info">点击三维场景中的设施查看对象信息</div>}
          </section>

          <section className="mine-hud-panel mine-research-panel">
            <div className="mine-hud-title mine-mapping-title">国自然项目场景映射
              <Popover title="空间场景说明" content={<div style={{ maxWidth: 340 }}>五钻孔区采用“水平钻孔—井下汇管—垂直抽采立管—地表井口”的空间关系；聚焦视图仅隐藏煤层目标层实体外壁，地面设施、井筒、巷道和其他矿井结构全部保留。</div>}><Button type="text" size="small">说明</Button></Popover>
            </div>
            <div className="research-chain">
              <div>矿井全局层</div><span>↓</span>
              <div>煤系气抽采系统层</div><span>↓</span>
              <div>五钻孔抽采与汇流</div><span>↓</span>
              <div>方案优选与物理校核</div>
            </div>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Button type="primary" block onClick={() => setPreset('drainage')}>聚焦五钻孔透视区</Button>
              <Button block onClick={onOpenPrediction}>进入方案预测与优选</Button>
              <Button block onClick={onOpenSimulation}>进入物理仿真中心</Button>
            </Space>
          </section>
        </aside>
      </div>
    </div>
  );
}
