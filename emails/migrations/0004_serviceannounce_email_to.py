# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-07-19 22:48
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0003_smsmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='serviceannounce',
            name='email_to',
            field=models.CharField(choices=[(b'lnl@wpi.edu', b'Exec Board'), (b'lnl-active@wpi.edu', b'Active Members'), (b'lnl-news@wpi.edu', b'LNL News'), (b'lnl-w@wpi.edu', b'Webmaster')], default=b'lnl@wpi.edu', max_length=24),
        ),
    ]
