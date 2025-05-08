from django.db import models

class Therapist(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    speciality = models.CharField(max_length=255, null=True, blank=True)
    external_id = models.IntegerField()
