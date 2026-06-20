import uuid
from django.db import models
from repository.models import Repository

class AnalysisReport(models.Model):
    report_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ai_model = models.CharField(max_length=100, default='')
    analysis_date = models.DateTimeField(auto_now_add=True)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='analysis_reports')

    def __str__(self):
        return f"Report {self.report_id} - {self.repository.repo_name}"

class CodeSmell(models.Model):
    smell_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    smell_type = models.CharField(max_length=100)
    severity_level = models.CharField(max_length=50) # Major, Moderate, Minor
    file_path = models.CharField(max_length=500)
    line_range = models.CharField(max_length=100, default='') 
    description = models.TextField()
    is_resolved = models.BooleanField(default=False)
    report = models.ForeignKey(AnalysisReport, on_delete=models.CASCADE, related_name='code_smells')

    def __str__(self):
        return f"{self.severity_level} {self.smell_type} in {self.file_path}"
