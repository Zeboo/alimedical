from django.db import models
from django.utils import timezone

class Patient(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    age = models.IntegerField()
    address = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return self.name


class Doctor(models.Model):
    name = models.CharField(max_length=100)
    fee = models.FloatField()

    def __str__(self):
        return self.name


class OPDVisit(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    token_number = models.IntegerField()
    fee = models.FloatField()
    discount = models.FloatField(default=0)
    total = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token_number:
            today = timezone.localdate()
            last_token = (
                OPDVisit.objects.filter(created_at__date=today)
                .order_by("-token_number")
                .values_list("token_number", flat=True)
                .first()
            )
            self.token_number = (last_token or 0) + 1

        if self.doctor_id:
            self.fee = self.doctor.fee

        self.discount = 0
        self.total = self.fee
        super().save(*args, **kwargs)