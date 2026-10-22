import React,{useEffect,useRef} from 'react';
import * as THREE from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls';

export default function TwinCenter(){
const box=useRef();

useEffect(()=>{
const scene=new THREE.Scene();
scene.background=new THREE.Color(0xf2f2f2);
const camera=new THREE.PerspectiveCamera(45,1.5,0.1,500);
camera.position.set(100,80,120);

const renderer=new THREE.WebGLRenderer({antialias:true});
renderer.setSize(700,450);
box.current.appendChild(renderer.domElement);

const controls=new OrbitControls(camera,renderer.domElement);

scene.add(new THREE.Mesh(
new THREE.BoxGeometry(40,15,80),
new THREE.MeshPhongMaterial({color:0x888888,transparent:true,opacity:.35})
));

for(let i=0;i<5;i++){
let p=new THREE.Mesh(
new THREE.CylinderGeometry(.5,.5,80,32),
new THREE.MeshPhongMaterial({color:0x0066ff})
);
p.rotation.x=Math.PI/2;
p.position.x=(i-2)*5;
scene.add(p);
}

scene.add(new THREE.AxesHelper(70));
scene.add(new THREE.AmbientLight(0xffffff));

function loop(){
requestAnimationFrame(loop);
controls.update();
renderer.render(scene,camera);
}
loop();
},[]);

return <div><h2>五钻孔煤层气数字孪生</h2><div ref={box}/></div>
}
