# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import DjangoUeditor.models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='tb_datapoint_list',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sh_id', models.IntegerField(db_index=True)),
                ('sh_sensor_id', models.IntegerField()),
                ('sh_timestamp', models.IntegerField()),
                ('sh_value', DjangoUeditor.models.UEditorField(default='', verbose_name='\u5185\u5bb9', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='tb_device',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sh_id', models.IntegerField(db_index=True)),
                ('sh_name', models.CharField(max_length=50)),
                ('sh_tags', models.CharField(max_length=50)),
                ('sh_locate', models.CharField(max_length=50)),
                ('sh_user_id', models.IntegerField()),
                ('sh_create_time', models.DateField()),
                ('sh_last_active', models.DateField()),
                ('sh_status', models.BooleanField(default=False)),
                ('sh_about', DjangoUeditor.models.UEditorField(default='', verbose_name='\u5185\u5bb9', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='tb_sensor',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sh_id', models.IntegerField(db_index=True)),
                ('sh_name', models.CharField(max_length=50)),
                ('sh_tags', models.CharField(max_length=50)),
                ('sh_type', models.IntegerField()),
                ('sh_device_id', models.IntegerField()),
                ('sh_last_update', models.DateField()),
                ('sh_last_data', models.TextField()),
                ('sh_status', models.BooleanField(default=False)),
                ('sh_about', DjangoUeditor.models.UEditorField(default='', verbose_name='\u5185\u5bb9', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='tb_sensor_type',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sh_id', models.IntegerField(db_index=True)),
                ('sh_name', models.CharField(max_length=50)),
                ('sh_description', models.TextField()),
                ('sh_status', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='tb_user',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sh_id', models.IntegerField(db_index=True)),
                ('sh_username', models.CharField(max_length=20)),
                ('sh_password', models.CharField(max_length=100)),
                ('sh_email', models.CharField(max_length=50)),
                ('sh_token', models.CharField(max_length=50)),
                ('sh_token_exptime', models.DateField()),
                ('sh_regtime', models.DateField()),
                ('sh_status', models.BooleanField(default=False)),
                ('sh_apikey', models.CharField(max_length=100)),
                ('sh_about', DjangoUeditor.models.UEditorField(default='', verbose_name='\u5185\u5bb9', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='tb_user_token',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sh_user_id', models.IntegerField(db_index=True)),
                ('sh_token', models.CharField(max_length=100)),
                ('sh_deadline', models.IntegerField()),
            ],
        ),
    ]
