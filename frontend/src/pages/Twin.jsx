
import React,{useEffect,useRef} from "react";
import * as THREE from "three";
import {OrbitControls} from "three/examples/jsm/controls/OrbitControls";


export default function Twin(){

const view=useRef();
const controlRef=useRef();


useEffect(()=>{


const scene=new THREE.Scene();

scene.background=
new THREE.Color(0xf2f2f2);



const camera=
new THREE.PerspectiveCamera(
45,
700/450,
0.1,
1000
);


camera.position.set(
90,
70,
120
);



const renderer=
new THREE.WebGLRenderer({
antialias:true
});


renderer.setSize(
700,
450
);


view.current.appendChild(
renderer.domElement
);



const controls=
new OrbitControls(
camera,
renderer.domElement
);


controls.enableDamping=true;

controlRef.current=controls;



// 煤层
scene.add(

new THREE.Mesh(

new THREE.BoxGeometry(
40,
15,
80
),

new THREE.MeshPhongMaterial({

color:0x888888,

transparent:true,

opacity:0.35

})

)

);



// 五根管道

for(let i=0;i<5;i++){

let pipe=
new THREE.Mesh(

new THREE.CylinderGeometry(
0.5,
0.5,
80,
32
),

new THREE.MeshPhongMaterial({

color:0x0066ff

})

);


pipe.rotation.x=Math.PI/2;


pipe.position.x=(i-2)*5;


scene.add(pipe);

}



scene.add(
new THREE.AxesHelper(70)
);


scene.add(
new THREE.AmbientLight(
0xffffff,
0.8
)
);



function animate(){

requestAnimationFrame(animate);

controls.update();

renderer.render(scene,camera);

}

animate();


},[]);


function reset(){

controlRef.current.reset();

}


return <>

<h1>五钻孔煤层气三维孪生</h1>

<button onClick={reset}>
恢复视角
</button>

<div ref={view}/>

</>

}
