# MulticsSmartHome

    该项目为在大四实习时自己使用Django 开发的一个小平台。		
    
    该项目模仿Yeelink,实现相应的接口,采用Python语言开发,Web框架使用的是Django.
    现在平台框架已大体做好，数据库和服务器都使用框架默认或自带的模块，后期需要进行开发的话需要进行MySQL，Nginx，Apache等配置或开发。

    构建开发及运行环境：
    1、安装Python；安装在need_install目录的python安装包，最好将2.7和3.5的都安装一下。
    2、安装Django；进入Django-1.8.17目录，命令行运行：python setup.py install
    2、安装Django-admin；这个是美化后台界面所需要的插件，进入django-admin-bootstrap/
       目录，命令行运行：python setup.py install.
    注：Linux和Mac用户可在终端直接运行命令进行安装；
        Ubuntu或Linux mint用户运行：“ sudo apt-get install 软件包名”
        CentOS用户直接运行：“ sudo yum install 软件包名”

    运行项目：
    在项目目录下面打开命令行窗口，运行以下命令：
    1、python manage.py makemigrations home
    2、python manage.py migrate
    3、python manage.py runserver 
       注：默认端口8000.如果提示端口被占用，可以运行：python manage.py runserver 8001

    在提示以下信息后
    $ python manage.py runserver
    Performing system checks...
    System check identified no issues (0 silenced).
    March 14, 2017 - 13:43:41
    Django version 1.8.17, using settings 'SmartHome.settings'
    Starting development server at http://127.0.0.1:8000/
    Quit the server with CTRL-BREAK.    
    打开浏览器，输入相应的URL即可访问，常用的URL如下：

    进入后台URL：http://127.0.0.1:8000/admin
        注：如果没有后台账号的话可以输入：python manage.py createsuperuser
            按提示创建相应的账号即可登录，也可以让管理员登录后台为你新建一个。

    开发的接口，可用浏览器进行测试。
    获取用户的详细信息：http://127.0.0.1:8000/sh_user/<user_id>
        eg:http://127.0.0.1:8000/sh_user/1/
    获取用户令牌的RUL：http://127.0.0.1:8000/sh_user_token/<user_id>
        eg:http://127.0.0.1:8000/sh_user_token/1/
    获取设备信息的URL：http://127.0.0.1:8000/sh_device/<device_id>
        eg:http://127.0.0.1:8000/sh_device/1/
    获取传感器信息的接口：http://127.0.0.1:8000/sh_sensor/<device_id>
        eg:http://127.0.0.1:8000/sh_sensor/1/
    获取传感器类型的接口：http://127.0.0.1:8000/sh_sensor_typer/<device_id>
        eg:http://127.0.0.1:8000/sh_sensor_type/1/
    数据点的接口：http://127.0.0.1:8000/sh_datapoint_list/<sensor_id>
        eg:http://127.0.0.1:8000/sh_datapoint_list/1/


参考博文：		

Django 中文文档 1.8：http://python.usyiyi.cn/django/index.html		

Django 基础教程（自强学堂）：http://www.ziqiangxuetang.com/django/django-tutorial.html		

谈谈互联网后端基础设施：http://www.rowkey.me/blog/2016/08/27/server-basic-tech-stack/		

智能家居云平台设计：http://www.cnblogs.com/star91/p/4889118.html		

