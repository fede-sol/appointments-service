from django.db import models
from therapists.models import Therapist

class Appointment(models.Model):
    begin_date = models.DateTimeField()
    end_date = models.DateTimeField()
    patient_id = models.IntegerField()
    patient_name = models.CharField(max_length=255)
    patient_email = models.EmailField()
    patient_phone = models.CharField(max_length=255)
    therapist = models.ForeignKey(Therapist, on_delete=models.CASCADE)
    status = models.CharField(max_length=255, default='programado')
    link = models.CharField(max_length=255,blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
