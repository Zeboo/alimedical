from django.contrib import admin
from django import forms
from django.db.models import Count, Sum
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from datetime import timedelta
import json
from .models import Patient, Doctor, OPDVisit


ADMIN_PANEL_NAME = "Ali Medical and Dental Complex Fateh Jang"


admin.site.site_header = ADMIN_PANEL_NAME
admin.site.site_title = ADMIN_PANEL_NAME
admin.site.index_title = ADMIN_PANEL_NAME


def get_admin_dashboard_context():
	current_date = timezone.localdate()
	current_datetime = timezone.localtime()
	visits = OPDVisit.objects.select_related("doctor", "patient")
	today_visits = visits.filter(created_at__date=current_date)
	month_visits = visits.filter(created_at__year=current_date.year, created_at__month=current_date.month)

	total_income = visits.aggregate(total_income=Sum("total"))["total_income"] or 0
	today_income = today_visits.aggregate(total_income=Sum("total"))["total_income"] or 0
	month_income = month_visits.aggregate(total_income=Sum("total"))["total_income"] or 0

	last_7_days = []
	for day_offset in range(6, -1, -1):
		day = current_date - timedelta(days=day_offset)
		day_queryset = visits.filter(created_at__date=day)
		last_7_days.append(
			{
				"label": day.strftime("%d %b"),
				"visit_count": day_queryset.count(),
				"income": day_queryset.aggregate(total_income=Sum("total"))["total_income"] or 0,
			}
		)

	max_visit_count = max((day["visit_count"] for day in last_7_days), default=0)
	for day in last_7_days:
		day["bar_height"] = int((day["visit_count"] / max_visit_count) * 100) if max_visit_count else 0

	top_doctors = list(
		visits.values("doctor__name")
		.annotate(visit_count=Count("id"), income=Sum("total"))
		.order_by("-income", "doctor__name")[:5]
	)

	max_doctor_income = max((doctor["income"] or 0 for doctor in top_doctors), default=0)
	for doctor in top_doctors:
		doctor["income"] = doctor["income"] or 0
		doctor["progress_width"] = int((doctor["income"] / max_doctor_income) * 100) if max_doctor_income else 0

	recent_visits = list(visits.order_by("-created_at")[:5])

	return {
		"generated_at": current_datetime,
		"total_patients": Patient.objects.count(),
		"total_doctors": Doctor.objects.count(),
		"total_visits": visits.count(),
		"total_income": total_income,
		"today_visits": today_visits.count(),
		"today_income": today_income,
		"month_income": month_income,
		"last_7_days": last_7_days,
		"top_doctors": top_doctors,
		"recent_visits": recent_visits,
	}


_original_each_context = admin.site.each_context


def _dashboard_each_context(request):
	context = _original_each_context(request)
	if getattr(request, "user", None) and request.user.is_superuser:
		context["dashboard"] = get_admin_dashboard_context()
	return context


admin.site.each_context = _dashboard_each_context

admin.site.register(Doctor)


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
	list_display = ("id", "name", "phone", "age", "address")
	search_fields = ("name", "phone", "address")
	fields = ("name", "phone", "age", "address")


class OPDVisitAdminForm(forms.ModelForm):
	class Meta:
		model = OPDVisit
		fields = "__all__"
		exclude = ("discount",)

	class Media:
		js = ("opd/js/opdvisit_admin_v4.js",)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		token_number_field = self.fields.get("token_number")
		if token_number_field:
			token_number_field.required = False

		doctor_field = self.fields.get("doctor")
		if doctor_field:
			doctor_fees = {
				str(doctor.id): doctor.fee for doctor in Doctor.objects.only("id", "fee")
			}
			doctor_widget = doctor_field.widget
			select_widget = getattr(doctor_widget, "widget", doctor_widget)
			select_widget.attrs["data-doctor-fees"] = json.dumps(doctor_fees)
			select_widget.attrs["onchange"] = (
				"const doctorFees = JSON.parse(this.dataset.doctorFees || '{}');"
				"const doctorFee = parseFloat(doctorFees[this.value]);"
				"const feeField = document.getElementById('id_fee');"
				"const totalField = document.getElementById('id_total');"
				"if (feeField && totalField) {"
				"if (!Number.isNaN(doctorFee)) {"
				"const normalizedFee = doctorFee.toFixed(2);"
				"feeField.value = normalizedFee;"
				"totalField.value = normalizedFee;"
				"} else { feeField.value = ''; totalField.value = ''; }"
				"}"
			)

		fee_field = self.fields.get("fee")
		if fee_field:
			fee_field.required = False
			fee_field.widget.attrs["readonly"] = True

		total_field = self.fields.get("total")
		if total_field:
			total_field.required = False
			total_field.widget.attrs["readonly"] = True

	def clean(self):
		cleaned_data = super().clean()

		doctor = cleaned_data.get("doctor")
		if doctor:
			cleaned_data["fee"] = doctor.fee
			cleaned_data["total"] = doctor.fee

		if not cleaned_data.get("token_number"):
			today = timezone.localdate()
			last_token = (
				OPDVisit.objects.filter(created_at__date=today)
				.order_by("-token_number")
				.values_list("token_number", flat=True)
				.first()
			)
			cleaned_data["token_number"] = (last_token or 0) + 1

		return cleaned_data


@admin.register(OPDVisit)
class OPDVisitAdmin(admin.ModelAdmin):
	form = OPDVisitAdminForm
	change_list_template = "admin/opd/opdvisit/change_list.html"
	list_display = ("id", "patient", "doctor", "token_number", "fee", "total", "created_at")
	list_filter = ("doctor", "created_at")
	search_fields = ("patient__name", "doctor__name", "token_number")
	date_hierarchy = "created_at"
	ordering = ("-created_at", "-token_number")
	list_select_related = ("patient", "doctor")
	fields = ("patient", "doctor", "token_number_display", "fee", "total", "created_at_display")
	readonly_fields = ("token_number_display", "created_at_display")

	def get_urls(self):
		urls = super().get_urls()
		custom_urls = [
			path(
				"<int:visit_id>/voucher/",
				self.admin_site.admin_view(self.voucher_view),
				name="opd_opdvisit_voucher",
			),
		]
		return custom_urls + urls

	def get_record_summary(self, queryset):
		return {
			"visit_count": queryset.count(),
			"total_income": queryset.aggregate(total_income=Sum("total"))["total_income"] or 0,
		}

	@admin.display(description="Token number")
	def token_number_display(self, obj):
		if obj and obj.pk:
			return obj.token_number

		today = timezone.localdate()
		last_token = (
			OPDVisit.objects.filter(created_at__date=today)
			.order_by("-token_number")
			.values_list("token_number", flat=True)
			.first()
		)
		return (last_token or 0) + 1

	@admin.display(description="Created at")
	def created_at_display(self, obj):
		if obj and obj.pk:
			return obj.created_at

		return timezone.localtime()

	def save_model(self, request, obj, form, change):
		obj.discount = 0
		super().save_model(request, obj, form, change)

	def response_add(self, request, obj, post_url_continue=None):
		action_markers = {"_addanother", "_continue", "_save"}
		has_action_marker = any(marker in request.POST for marker in action_markers)

		if "_addanother" in request.POST or not has_action_marker:
			voucher_url = reverse("admin:opd_opdvisit_voucher", args=[obj.pk])
			add_visit_url = reverse("admin:opd_opdvisit_add")
			return HttpResponseRedirect(f"{voucher_url}?next={add_visit_url}")

		return super().response_add(request, obj, post_url_continue=post_url_continue)

	def voucher_view(self, request, visit_id):
		visit = self.get_object(request, str(visit_id))
		if visit is None:
			raise Http404("OPD visit not found")

		next_url = request.GET.get("next") or reverse("admin:opd_opdvisit_add")
		context = {
			**self.admin_site.each_context(request),
			"opts": self.model._meta,
			"visit": visit,
			"next_url": next_url,
			"title": "Print OPD Voucher",
		}
		return TemplateResponse(request, "admin/opd/opdvisit/voucher.html", context)

	def changelist_view(self, request, extra_context=None):
		extra_context = extra_context or {}
		response = super().changelist_view(request, extra_context=extra_context)

		if hasattr(response, "context_data") and response.context_data.get("cl"):
			response.context_data["record_summary"] = self.get_record_summary(response.context_data["cl"].queryset)

		return response