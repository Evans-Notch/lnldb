# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-12-26 22:43
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('events', '0024_rename_billed_by_semester'),
    ]

    operations = [
        migrations.CreateModel(
            name='PostEventSurvey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('services_quality', models.IntegerField(choices=[(0, b'Poor'), (1, b'Fair'), (2, b'Good'), (3, b'Very good'), (4, b'Excellent'), (-1, b'No basis to judge')], verbose_name=b'Please rate the overall quality of the services Lens and Lights provided.')),
                ('lighting_quality', models.IntegerField(choices=[(0, b'Poor'), (1, b'Fair'), (2, b'Good'), (3, b'Very good'), (4, b'Excellent'), (-1, b'No basis to judge')], verbose_name=b'How did the lighting look? If we did not provide lighting, choose "No basis to judge".')),
                ('sound_quality', models.IntegerField(choices=[(0, b'Poor'), (1, b'Fair'), (2, b'Good'), (3, b'Very good'), (4, b'Excellent'), (-1, b'No basis to judge')], verbose_name=b'How did the sound system sound? If we did not provide sound, choose "No basis to judge".')),
                ('work_order_method', models.IntegerField(choices=[(1, b'Via the website at lnl.wpi.edu/workorder'), (2, b'Emailed lnl@wpi.edu'), (3, b'Emailed an LNL representative directly'), (4, b'By phone'), (5, b'In person'), (0, b'Other'), (-1, b"I don't know")], verbose_name=b'How did you submit the work order?')),
                ('work_order_experience', models.IntegerField(choices=[(0, b'Poor'), (1, b'Fair'), (2, b'Good'), (3, b'Very good'), (4, b'Excellent'), (-1, b'No basis to judge')], verbose_name=b'How was your experience submitting the work order?')),
                ('communication_responsiveness', models.IntegerField(choices=[(0, b'Strongly disagree'), (1, b'Disagree'), (2, b'Neither agree nor disagree'), (3, b'Agree'), (4, b'Strongly agree'), (-1, b'No basis to judge')], verbose_name=b'Lens and Lights was responsive to my communications.')),
                ('pricelist_ux', models.IntegerField(choices=[(0, b'Strongly disagree'), (1, b'Disagree'), (2, b'Neither agree nor disagree'), (3, b'Agree'), (4, b'Strongly agree'), (-1, b'No basis to judge')], verbose_name=b'It was easy to determine which services to request.')),
                ('setup_on_time', models.IntegerField(choices=[(0, b'Strongly disagree'), (1, b'Disagree'), (2, b'Neither agree nor disagree'), (3, b'Agree'), (4, b'Strongly agree'), (-1, b'No basis to judge')], verbose_name=b'My event was set up on time.')),
                ('crew_respectfulness', models.IntegerField(choices=[(0, b'Strongly disagree'), (1, b'Disagree'), (2, b'Neither agree nor disagree'), (3, b'Agree'), (4, b'Strongly agree'), (-1, b'No basis to judge')], verbose_name=b'The crew was respectful of my property and of other people.')),
                ('crew_preparedness', models.IntegerField(choices=[(0, b'Strongly disagree'), (1, b'Disagree'), (2, b'Neither agree nor disagree'), (3, b'Agree'), (4, b'Strongly agree'), (-1, b'No basis to judge')], verbose_name=b'The crew was prepared.')),
                ('crew_knowledgeability', models.IntegerField(choices=[(0, b'Strongly disagree'), (1, b'Disagree'), (2, b'Neither agree nor disagree'), (3, b'Agree'), (4, b'Strongly agree'), (-1, b'No basis to judge')], verbose_name=b'The crew was knowledgeable.')),
                ('quote_as_expected', models.IntegerField(choices=[(0, b'Strongly disagree'), (1, b'Disagree'), (2, b'Neither agree nor disagree'), (3, b'Agree'), (4, b'Strongly agree'), (-1, b'No basis to judge')], verbose_name=b'The price quoted for the event matched my expectations.')),
                ('bill_as_expected', models.IntegerField(choices=[(0, b'Strongly disagree'), (1, b'Disagree'), (2, b'Neither agree nor disagree'), (3, b'Agree'), (4, b'Strongly agree'), (-1, b'No basis to judge')], verbose_name=b'The charges on the invoice matched my expectations.')),
                ('price_appropriate', models.IntegerField(choices=[(0, b'Strongly disagree'), (1, b'Disagree'), (2, b'Neither agree nor disagree'), (3, b'Agree'), (4, b'Strongly agree'), (-1, b'No basis to judge')], verbose_name=b'The price is appropriate for the services provided.')),
                ('customer_would_return', models.IntegerField(choices=[(0, b'Strongly disagree'), (1, b'Disagree'), (2, b'Neither agree nor disagree'), (3, b'Agree'), (4, b'Strongly agree'), (-1, b'No basis to judge')], verbose_name=b'I would use Lens and Lights in the future.')),
                ('comments', models.TextField(blank=True, verbose_name=b'Please use this area to explain low ratings above or to provide any other feedback you have. We value your feedback and will use it to improve our services.')),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='surveys', to='events.BaseEvent')),
                ('person', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='surveys', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['event', 'person'],
                'permissions': (('view_posteventsurvey', 'View post-event survey results'),),
            },
        ),
    ]
