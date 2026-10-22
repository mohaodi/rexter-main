import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { Button, Space, Tag } from 'antd';

export default function ThreeTwinPanel({ definition }) {
  const mountRef = useRef(null);
  const controlsRef = useRef(null);
  const cameraRef = useRef(null);

  useEffect(() => {
    if (!definition || !mountRef.current) return undefined;

    const container = mountRef.current;
    container.innerHTML = '';

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf3f5f7);

    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 1000);
    camera.position.set(72, 54, 115);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.055;
    controlsRef.current = controls;

    const geometry = definition.geometry || {};
    const box = geometry.display_box_m || { x: 40, y: 15, z: 80 };
    const modelGroup = new THREE.Group();

    const coal = new THREE.Mesh(
      new THREE.BoxGeometry(box.x, box.y, box.z),
      new THREE.MeshPhongMaterial({
        color: 0x7e8792,
        transparent: true,
        opacity: 0.30,
        side: THREE.DoubleSide,
      }),
    );
    modelGroup.add(coal);

    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(box.x, box.y, box.z)),
      new THREE.LineBasicMaterial({ color: 0x5b6673, transparent: true, opacity: 0.55 }),
    );
    modelGroup.add(edges);

    const displayRadius = 0.42;
    (geometry.three_positions || []).forEach((p) => {
      const pipe = new THREE.Mesh(
        new THREE.CylinderGeometry(displayRadius, displayRadius, geometry.borehole_length_m || 80, 32),
        new THREE.MeshPhongMaterial({ color: 0x0b5bd3, shininess: 55 }),
      );
      pipe.rotation.x = Math.PI / 2;
      pipe.position.set(p.x, p.y, p.z);
      modelGroup.add(pipe);
    });

    scene.add(modelGroup);
    scene.add(new THREE.AxesHelper(58));
    scene.add(new THREE.AmbientLight(0xffffff, 1.25));
    const light = new THREE.DirectionalLight(0xffffff, 1.1);
    light.position.set(60, 100, 80);
    scene.add(light);

    const resize = () => {
      const w = Math.max(container.clientWidth, 1);
      const h = Math.max(container.clientHeight, 1);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.zoom = Math.min(1, camera.aspect / 1.05);
      camera.updateProjectionMatrix();
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);

    let frame = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === container) container.removeChild(renderer.domElement);
    };
  }, [definition]);

  const resetView = () => {
    if (!controlsRef.current || !cameraRef.current) return;
    cameraRef.current.position.set(72, 54, 115);
    controlsRef.current.target.set(0, 0, 0);
    controlsRef.current.update();
  };

  return (
    <div className="three-panel-wrap">
      <div className="panel-toolbar">
        <Space wrap size={4}>
          <Tag color="blue">5 钻孔</Tag>
          <Tag>间距 5 m</Tag>
          <Tag>蓝色轴 Z = 长度方向</Tag>
        </Space>
        <Button size="small" onClick={resetView}>恢复初始视角</Button>
      </div>
      <div className="three-canvas" ref={mountRef} />
    </div>
  );
}
