import React,{useEffect,useRef} from 'react';
import * as THREE from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls.js';

function makeTube(a,b,r,color){
 const d=new THREE.Vector3().subVectors(b,a);
 const mesh=new THREE.Mesh(
   new THREE.CylinderGeometry(r,r,d.length(),24),
   new THREE.MeshStandardMaterial({color,roughness:.45})
 );
 mesh.position.copy(a).add(b).multiplyScalar(.5);
 mesh.quaternion.setFromUnitVectors(
   new THREE.Vector3(0,1,0),
   d.clone().normalize()
 );
 return mesh;
}

/*
  方案预测三维数字孪生
  与物理仿真中心保持一致：
  1. 灰色煤层块
  2. 单根中心水平主孔
  3. 每个钻孔位置生成一组 V 型子管
  4. 子管沿 z 轴负方向(煤层内部)倾斜
  5. 子管长度受煤层厚度限制
*/

export default function SchemeTwin({boreholes=[],inclination=20,length=120}){

 const ref=useRef();

 useEffect(()=>{
  const el=ref.current;
  if(!el)return;
  el.innerHTML='';

  const scene=new THREE.Scene();
  scene.background=new THREE.Color(0xf3f5f7);

  const camera=new THREE.PerspectiveCamera(38,1,0.1,500);
  camera.position.set(95,65,125);

  const renderer=new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
  el.appendChild(renderer.domElement);

  const controls=new OrbitControls(camera,renderer.domElement);
  controls.enableDamping=true;
  controls.target.set(0,-20,0);
  controls.update();

  // 与物理仿真中心一致的煤层尺寸
  const coalSize={x:100,y:30,z:60};

  const coal=new THREE.Mesh(
    new THREE.BoxGeometry(coalSize.x,coalSize.y,coalSize.z),
    new THREE.MeshStandardMaterial({
      color:0x9b9187,
      transparent:true,
      opacity:.42
    })
  );
  coal.position.set(0,-20,0);
  scene.add(coal);


  // 中心水平主孔
  const mainY=-7;
  const mainZ=0;

  scene.add(makeTube(
    new THREE.Vector3(-38,mainY,mainZ),
    new THREE.Vector3(38,mainY,mainZ),
    1.3,
    0x0055aa
  ));


  // 钻孔数量 = V型子管组数量
  const groups=Math.max(
    Number(boreholes?.length)||Number(boreholes)||3,
    1
  );


  // 子管只显示示意长度，不能穿出煤层
  const angle=Number(inclination||20)*Math.PI/180;

  const maxDepth=coalSize.y*0.7;
  const depth=Math.min(
    maxDepth,
    Math.max(8,length*0.12)
  );


  // 沿x方向布置多组
  const positions=[];
  if(groups===1){
    positions.push(0);
  }else{
    for(let i=0;i<groups;i++){
      positions.push(
        -30+i*(60/(groups-1))
      );
    }
  }


  positions.forEach(x=>{

    const start=new THREE.Vector3(
      x,
      mainY,
      mainZ
    );

    /*
      每一组子管按该组主孔轴方向旋转90°：
      - 主孔沿 X 方向
      - 子管原始 V 型位于主孔局部截面
      - 旋转后保持左右展开、同时向煤层内部(Y负方向)下探
      - 长度限制在煤层内部
    */
    // 主管沿 X 轴，因此每一组子管必须旋转到与主管垂直的 YZ 截面。
    // 不再沿 X 方向展开，而是在固定 x 截面内形成 V 型。
    const vertical=Math.min(
      coalSize.y*0.55,
      Math.max(10, Math.cos(angle)*depth*0.45)
    );

    const side=Math.min(
      coalSize.z*0.28,
      Math.max(8, Math.sin(angle)*depth*0.45)
    );

    const left=new THREE.Vector3(
      x,
      mainY-vertical,
      mainZ-side
    );

    const right=new THREE.Vector3(
      x,
      mainY-vertical,
      mainZ+side
    );

    scene.add(makeTube(start,left,1.05,0x0055aa));
    scene.add(makeTube(start,right,1.05,0x0055aa));

  });



  scene.add(new THREE.AmbientLight(0xffffff,1.5));
  const light=new THREE.DirectionalLight(0xffffff,1);
  light.position.set(50,100,80);
  scene.add(light);


  const resize=()=>{
    const w=el.clientWidth||650;
    const h=el.clientHeight||420;
    renderer.setSize(w,h,false);
    camera.aspect=w/h;
    camera.zoom=Math.min(1,camera.aspect/1.15);
    camera.updateProjectionMatrix();
  };

  const observer=new ResizeObserver(resize);
  observer.observe(el);
  resize();

  let frame;
  const animate=()=>{
    frame=requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene,camera);
  };
  animate();

  return()=>{
    cancelAnimationFrame(frame);
    observer.disconnect();
    controls.dispose();
    renderer.dispose();
    el.innerHTML='';
  }

 },[boreholes,inclination,length]);

 return <div ref={ref} className="scheme-three-canvas" style={{width:'100%',flex:1,minHeight:0}}/>;
}
