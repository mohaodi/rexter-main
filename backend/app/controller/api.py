
from fastapi import APIRouter
from pydantic import BaseModel
import math

router=APIRouter(prefix='/api')


class Predict(BaseModel):
    pressure:float
    days:int


@router.get('/dashboard')
def dashboard():
    return {
        'wells':5,
        'pressure':40,
        'gas':12.5,
        'flow':350,
        'simulation':2
    }


@router.get('/curve')
def curve():
    return {
        'time':[0,30,60,90,120],
        'pressure':[40,38,35,32,30],
        'gas':[12.5,11.8,11,10.2,9.6],
        'flow':[350,330,300,280,250]
    }


@router.get('/twin')
def twin():
    return {
        'layer':{
            'size':[100,30,100]
        },
        'wells':[
            {'x':0,'y':0,'z':0},
            {'x':20,'y':0,'z':0},
            {'x':-20,'y':0,'z':0},
            {'x':0,'y':20,'z':0},
            {'x':0,'y':-20,'z':0}
        ]
    }


@router.post('/predict')
def predict(data:Predict):
    return {
        'model':'Surrogate',
        'result':data.pressure*math.sqrt(data.days)*0.00002
    }


@router.post('/simulation/start')
def simulation():
    return {
        'task':'COMSOL-001',
        'status':'running',
        'progress':0
    }


@router.get('/history')
def history():
    return [
        {'date':'2026-01-01','result':80},
        {'date':'2026-02-01','result':90}
    ]
