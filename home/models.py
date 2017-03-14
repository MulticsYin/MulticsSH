# _*_ coding: utf-8 _*_
from __future__ import unicode_literals
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from DjangoUeditor.models import UEditorField
from django.core.urlresolvers import reverse

# 用户表（tb_user），用于保存用户的基本信息。
@python_2_unicode_compatible
class tb_user(models.Model):
    sh_id = models.IntegerField(db_index=True) #用户ID
    sh_username = models.CharField(max_length=20) #用户名
    sh_password = models.CharField(max_length=100) #密码密文
    sh_email = models.CharField(max_length=50) #验证邮箱
    sh_token = models.CharField(max_length=50) #验证令牌
    sh_token_exptime = models.DateField() #令牌失效时间
    sh_regtime = models.DateField() #注册时间戳
    sh_status = models.BooleanField(default=False) #状态：激活与否
    sh_apikey = models.CharField(max_length=100) #APIKEY，用于授权API操作
    sh_about = UEditorField('内容', height=300, width=1000,default=u'', blank=True, 
            imagePath="uploads/images/",toolbars='besttome', filePath='uploads/files/') #描述
    def __str__(self):
        return self.sh_username
#    def get_absolute_url(self):
#        return reverse('tb_user', args=(self.sh_id,))
    
# 用户令牌表（tb_user_token)用于保存用户的令牌，该令牌在用户每次登陆时重新
# 生成，并确保唯一，一定时间后会自动失效，需要重新登陆。
@python_2_unicode_compatible
class tb_user_token(models.Model):
    sh_user_id = models.IntegerField(db_index=True) #用户ID
    sh_token = models.CharField(max_length=100) #用户令牌
    sh_deadline = models.IntegerField() #截止时间、失效时间
    def __str__(self):
        return self.sh_token

# 设备表（tb_device）用于保存无线智能家居系统设备信息。
@python_2_unicode_compatible
class tb_device(models.Model):
    sh_id = models.IntegerField(db_index=True) #设备ID
    sh_name = models.CharField(max_length=50) #设备名称
    sh_tags = models.CharField(max_length=50) #设备标签
    sh_locate = models.CharField(max_length=50) #设备位置
    sh_user_id = models.IntegerField() #用户ID
    sh_create_time = models.DateField() #创建时间
    sh_last_active = models.DateField() #最后活动时间
    sh_status = models.BooleanField(default=False) #状态
    sh_about = UEditorField('内容', height=300, width=1000,default=u'', blank=True,
            imagePath="uploads/images/",toolbars='besttome', filePath='uploads/files/') #描述
    def __str__(self):
        return self.sh_name

# 传感器表（tb_sensor）用于保存无线智能家居系统设备所包含的传感器的信息，
# 一个设备可能包含有多个传感器。
@python_2_unicode_compatible
class tb_sensor(models.Model):
    sh_id = models.IntegerField(db_index=True) #传感器ID
    sh_name = models.CharField(max_length=50) #传感器名称
    sh_tags = models.CharField(max_length=50) #传感器标签
    sh_type = models.IntegerField() #传感器类型ID
    sh_device_id = models.IntegerField() #设备ID
    sh_last_update = models.DateField() #更新时间
    sh_last_data = models.TextField() #最新数据
    sh_status = models.BooleanField(default=False) #状态
    sh_about = UEditorField('内容', height=300, width=1000,default=u'', blank=True,
            imagePath="uploads/images/",toolbars='besttome', filePath='uploads/files/') #描述
    def __str__(self):
        return self.sh_name

# 传感器类型表（tb_sensor_type）用于保存传感器的类型及描述，创建该表的目
# 的在于方便扩展传感器类型。
@python_2_unicode_compatible
class tb_sensor_type(models.Model):
    sh_id = models.IntegerField(db_index=True) #传感器类型ID
    sh_name = models.CharField(max_length=50) #类型名称
    sh_description = models.TextField() #对该类型的描述
    sh_status = models.BooleanField(default=False) #状态
    def __str__(self):
        return self.sh_name

# 数据点表（tb_datapoint_lite）用于保存传感器的数据，每一条记录都是某个传
# 感器的某个时间点下的数据。
@python_2_unicode_compatible
class tb_datapoint_list(models.Model):
    sh_id = models.IntegerField(db_index=True) #数据点ID
    sh_sensor_id = models.IntegerField() #传感器ID
    sh_timestamp = models.IntegerField() #时间戳
    sh_value = UEditorField('内容', height=300, width=1000,default=u'', blank=True,
            imagePath="uploads/images/",toolbars='besttome', filePath='uploads/files/') #数据值
    def __str__(self):
        return self.sh_value
