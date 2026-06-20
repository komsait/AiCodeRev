from django.contrib import admin
from .models import AnalysisReport, CodeSmell

@admin.register(AnalysisReport)
class AnalysisReportAdmin(admin.ModelAdmin):
    list_display = ('report_id', 'repository', 'ai_model', 'analysis_date')
    list_filter = ('ai_model', 'analysis_date')

@admin.register(CodeSmell)
class CodeSmellAdmin(admin.ModelAdmin):
    list_display = ('smell_type', 'severity_level', 'file_path', 'report')
    search_fields = ('smell_type', 'file_path')
    list_filter = ('severity_level',)
