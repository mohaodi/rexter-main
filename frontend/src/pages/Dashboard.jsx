
import React,{useEffect,useState} from 'react';
import request from '../api/request';

export default function Dashboard(){

const [d,setD]=useState({});

useEffect(()=>{
request.get('/dashboard').then(r=>setD(r.data))
},[]);

return <div>
<h1>煤系气抽采综合监控中心</h1>

<div>
钻孔:{d.wells}
&nbsp;&nbsp;
负压:{d.pressure}kPa
&nbsp;&nbsp;
瓦斯:{d.gas}%
&nbsp;&nbsp;
流量:{d.flow}m3/d
</div>

</div>
}
