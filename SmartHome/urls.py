# _*_ coding: utf-8 _*_
"""SmartHome URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic.base import RedirectView
from DjangoUeditor import urls as DjangoUeditor_urls
#use Django server /media/ files
from django.conf import settings
from home import views

# 定义添加各接口的URL。
urlpatterns = [
    # 定义后台URLhttp://127.0.0.1:8000/admin
    url(r'^admin/', include(admin.site.urls)),

    # 此为使用插件优化输入文本框所添加的。
    url(r'^ueditor/', include(DjangoUeditor_urls)),

    # 定义主界面的URL，由于不涉及前端开发，故只有相应的接口。
    url(r'^$',views.index,name = 'index'),

    # 定义URL获取用户的详细信息：http://127.0.0.1:8000/sh_user/<user_id>
    url(r'^sh_user/(?P<sh_id>[^/]+)/$',views.sh_user,name = 'sh_user'),

    # 定义获取用户令牌的RUL：http://127.0.0.1:8000/sh_user_token/<user_id>
    url(r'^sh_user_token/(?P<sh_user_id>[^/]+)/$',views.sh_user_token,name = 'sh_user_token'),

    # 定义获取设备信息的URL：http://127.0.0.1:8000/sh_device/<device_id>
    url(r'^sh_device/(?P<sh_id>[^/]+)/$',views.sh_device,name = 'sh_device'),

    # 定义获取传感器信息的接口：http://127.0.0.1:8000/sh_sensor/<device_id>
    url(r'^sh_sensor/(?P<sh_id>[^/]+)/$',views.sh_sensor,name = 'sh_sensor'),

    # 定义获取传感器类型的接口：http://127.0.0.1:8000/sh_sensor_typer/<device_id>
    url(r'^sh_sensor_type/(?P<sh_id>[^/]+)/$',views.sh_sensor_type,name = 'sh_sensor_type'),

    # 定义数据点的接口：http://127.0.0.1:8000/sh_datapoint_list/<sensor_id>
    url(r'^sh_datapoint_list/(?P<sh_id>[^/]+)/$',views.sh_datapoint_list,name = 'sh_datapoint_list'),
]

# 添加文本框优化时添加的设置。
if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
