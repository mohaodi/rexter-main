
import math


class TwinEngine:


    def geometry(self):

        wells=[]

        for i in range(5):

            wells.append({

                "id":f"Well-{i+1}",

                # 展示坐标:
                # X:管间距
                # Y:高度
                # Z:长度方向

                "x":(i-2)*5,

                "y":7.5,

                "z":0,

                "length":80

            })


        return {

            "coal":{

                "length":80,

                "width":40,

                "height":15

            },

            "wells":wells

        }



    def simulate(self,pressure,days):

        result=[]

        for d in range(days+1):

            result.append({

                "day":d,

                "pressure":
                pressure*(1-0.5*d/days),

                "gas":
                100*math.exp(-0.01*d),

                "flow":
                300*math.exp(-0.005*d)

            })

        return result
