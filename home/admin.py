#_*_ coding: utf-8 _*_
from django.contrib import admin
from .models import *

# Register your models heore.
# 两种方法建立数据库与后台的连接
# 本机登录http://127.0.0.1:8000/admin/即可访问后台，前提是使用python manage.py runserver.
# 若无管理员，在项目当前目录命令行下输入python manage.py createsuperuser新建管理员。
# 方法一：
class tb_userAdmin(admin.ModelAdmin):
    list_display = ('sh_id','sh_username','sh_password','sh_email','sh_token','sh_token_exptime','sh_regtime','sh_status','sh_apikey','sh_about')
class tb_user_tokenAdmin(admin.ModelAdmin):
    list_display = ('sh_user_id','sh_token','sh_deadline')
class tb_deviceAdmin(admin.ModelAdmin):
    list_display = ('sh_id','sh_name','sh_tags','sh_locate','sh_about','sh_user_id','sh_create_time','sh_last_active','sh_status')
class tb_sensorAdmin(admin.ModelAdmin):
    list_display = ('sh_id','sh_name','sh_tags','sh_type','sh_about','sh_device_id','sh_last_update','sh_last_data','sh_status')
class tb_sensor_typeAdmin(admin.ModelAdmin):
    list_display = ('sh_id','sh_name','sh_description','sh_status')
class tb_datapoint_listAdmin(admin.ModelAdmin):
    list_display = ('sh_id','sh_sensor_id','sh_timestamp','sh_value')

admin.site.register(tb_user, tb_userAdmin)
admin.site.register(tb_user_token, tb_user_tokenAdmin)
admin.site.register(tb_device, tb_deviceAdmin)
admin.site.register(tb_sensor, tb_sensorAdmin)
admin.site.register(tb_sensor_type, tb_sensor_typeAdmin)
admin.site.register(tb_datapoint_list, tb_datapoint_listAdmin)


# 方法二：
'''
admin.site.register(tb_user)
admin.site.register(tb_user_token)
admin.site.register(tb_device)
admin.site.register(tb_sensor)
admin.site.register(tb_sensor_type)
admin.site.register(tb_datapoint_list)
'''
