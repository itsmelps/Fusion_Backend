# Generated migration for SPACS module enhancements
from django.db import migrations, models
import django.db.models.deletion
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('scholarships', '0003_mcm_extra_documents'),
        ('globals', '0001_initial'),
        ('academic_information', '0001_initial'),
    ]

    operations = [
        # Add fields to Award_and_scholarship
        migrations.AddField(
            model_name='award_and_scholarship',
            name='publish_flag',
            field=models.BooleanField(default=True, help_text='Only published awards appear in application flows.'),
        ),
        migrations.AddField(
            model_name='award_and_scholarship',
            name='version',
            field=models.IntegerField(default=1, help_text='Incremented each time catalog text is saved.'),
        ),
        migrations.AddField(
            model_name='award_and_scholarship',
            name='cpi_cutoff',
            field=models.FloatField(default=0.0, help_text='Minimum CPI required. 0 means no CPI requirement.'),
        ),
        migrations.AddField(
            model_name='award_and_scholarship',
            name='income_ceiling',
            field=models.IntegerField(default=0, help_text='Maximum annual family income in rupees. 0 means no ceiling.'),
        ),
        migrations.AddField(
            model_name='award_and_scholarship',
            name='eligible_programme',
            field=models.CharField(default='all', help_text="e.g. 'B.Tech' or 'all'", max_length=50),
        ),
        
        # Create Withdrawal model
        migrations.CreateModel(
            name='Withdrawal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scholarship_type', models.CharField(choices=[('mcm', 'MCM Scholarship'), ('gold', "Director's Gold Medal"), ('silver', "Director's Silver Medal"), ('dm', 'D&M Proficiency Gold Medal')], max_length=10)),
                ('application_id', models.IntegerField()),
                ('reason', models.TextField(max_length=1000)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('acknowledged', models.BooleanField(default=False)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('acknowledged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='withdrawal_acknowledgements', to='globals.ExtraInfo')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='academic_information.Student')),
            ],
            options={
                'db_table': 'Withdrawal',
            },
        ),
        
        # Create ApplicationDraft model
        migrations.CreateModel(
            name='ApplicationDraft',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('award_type', models.CharField(max_length=30)),
                ('draft_data', models.TextField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='academic_information.Student')),
            ],
            options={
                'db_table': 'ApplicationDraft',
                'unique_together': {('student', 'award_type')},
            },
        ),
        
        # Create ApplicationForward model
        migrations.CreateModel(
            name='ApplicationForward',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scholarship_type', models.CharField(choices=[('mcm', 'MCM'), ('gold', 'Gold'), ('silver', 'Silver'), ('dm', 'DM')], max_length=10)),
                ('application_id', models.IntegerField()),
                ('notes', models.TextField(blank=True, default='', max_length=500)),
                ('forwarded_at', models.DateTimeField(auto_now_add=True)),
                ('forwarded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='forwarded_applications', to='globals.ExtraInfo')),
            ],
            options={
                'db_table': 'ApplicationForward',
                'unique_together': {('scholarship_type', 'application_id')},
            },
        ),
        
        # Create StudentDocument model
        migrations.CreateModel(
            name='StudentDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('doc_type', models.CharField(choices=[('income_certificate', 'Income Certificate'), ('marksheet', 'Marksheet'), ('fee_receipt', 'Fee Receipt'), ('bank_details', 'Bank Details'), ('affidavit', 'Affidavit'), ('aadhar_card', 'Aadhar Card'), ('relevant_document', 'Relevant Document')], max_length=30)),
                ('file', models.FileField(upload_to='student_documents/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('valid_until', models.DateField(blank=True, null=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='academic_information.Student')),
            ],
            options={
                'db_table': 'StudentDocument',
            },
        ),
    ]
