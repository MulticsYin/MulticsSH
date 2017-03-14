#_*_ coding:utf-8 _*_
from django.shortcuts import render
from django.http import HttpResponse
from .models import *
from django.shortcuts import redirect
# Create your views here.
#主目录，本项目不涉及前端，故只保留一个接口而不进行开发。
def index(request):
    return HttpResponse(u'Welcome to gree Smart Home...')

# 定义用户信息返回的函数。
def sh_user(request,sh_id):
    column = tb_user.objects.get(sh_id = sh_id)
    return render(request, 'home/sh_user.html', {'tb_user': column})

# 定义用户令牌返回的函数。
def sh_user_token(request,sh_user_id):
    column = tb_user_token.objects.get(sh_user_id = sh_user_id)
    return render(request, 'home/sh_user_token.html', {'tb_user_token': column})

# 定义设备信息返回的函数。
def sh_device(request,sh_id):
    column = tb_device.objects.get(sh_id = sh_id)
    return render(request, 'home/sh_device.html', {'tb_device': column})

# 定义传感器返回的函数。
def sh_sensor(request,sh_id):
    column = tb_sensor.objects.get(sh_id = sh_id)
    return render(request, 'home/sh_sensor.html', {'tb_sensor': column})

# 定义传感器返回类型的函数。
def sh_sensor_type(request,sh_id):
    column = tb_sensor_type.objects.get(sh_id = sh_id)
    return render(request, 'home/sh_sensor_type.html', {'tb_sensor_type': column})

# 定义数据点的返回函数。
def sh_datapoint_list(request,sh_id):
    column = tb_datapoint_list.objects.get(sh_id = sh_id)
    return render(request, 'home/sh_datapoint_list.html', {'tb_datapoint_list': column})
