from django.test import TestCase
from django.utils import timezone
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.test import RequestFactory
from django.urls import reverse
from datetime import timedelta
import json

from .admin import ADMIN_PANEL_NAME, OPDVisitAdminForm, OPDVisitAdmin, get_admin_dashboard_context
from .models import Doctor, OPDVisit, Patient


class OPDVisitTests(TestCase):
	def setUp(self):
		self.patient = Patient.objects.create(name="Test Patient", phone="9999999999", age=30)
		self.doctor = Doctor.objects.create(name="Dr. Strange", fee=500)

	def test_visit_fee_total_and_discount_are_auto_set(self):
		visit = OPDVisit.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			token_number=1,
			fee=10,
			discount=50,
			total=0,
		)

		self.assertEqual(visit.fee, 500)
		self.assertEqual(visit.discount, 0)
		self.assertEqual(visit.total, 500)

	def test_admin_form_does_not_show_discount_field(self):
		form = OPDVisitAdminForm()
		self.assertNotIn("discount", form.fields)

	def test_admin_form_init_works_when_token_number_is_excluded(self):
		class OPDVisitAdminFormWithoutToken(OPDVisitAdminForm):
			class Meta(OPDVisitAdminForm.Meta):
				exclude = ("discount", "token_number")

		form = OPDVisitAdminFormWithoutToken()
		self.assertNotIn("token_number", form.fields)

	def test_admin_form_injects_doctor_fee_mapping(self):
		form = OPDVisitAdminForm()
		doctor_fees_json = form.fields["doctor"].widget.attrs.get("data-doctor-fees")
		self.assertIsNotNone(doctor_fees_json)
		doctor_fees = json.loads(doctor_fees_json)
		self.assertEqual(doctor_fees[str(self.doctor.id)], self.doctor.fee)
		self.assertIn("onchange", form.fields["doctor"].widget.attrs)
		self.assertIn("id_fee", form.fields["doctor"].widget.attrs["onchange"])
		self.assertIn("id_total", form.fields["doctor"].widget.attrs["onchange"])

	def test_model_admin_form_attaches_fee_mapping_to_actual_select(self):
		admin_instance = OPDVisitAdmin(OPDVisit, AdminSite())
		form = admin_instance.get_form(None)()
		doctor_widget = form.fields["doctor"].widget
		select_widget = getattr(doctor_widget, "widget", doctor_widget)
		doctor_fees_json = select_widget.attrs.get("data-doctor-fees")

		self.assertIsNotNone(doctor_fees_json)
		doctor_fees = json.loads(doctor_fees_json)
		self.assertEqual(doctor_fees[str(self.doctor.id)], self.doctor.fee)
		self.assertIn("onchange", select_widget.attrs)

	def test_admin_form_fee_and_total_are_readonly(self):
		form = OPDVisitAdminForm()
		self.assertIn("readonly", form.fields["fee"].widget.attrs)
		self.assertIn("readonly", form.fields["total"].widget.attrs)

	def test_admin_token_and_created_at_display_for_add_form(self):
		admin_instance = OPDVisitAdmin(OPDVisit, AdminSite())
		next_token = admin_instance.token_number_display(None)
		created_at_value = admin_instance.created_at_display(None)

		self.assertEqual(next_token, 1)
		self.assertIsNotNone(created_at_value)

	def test_token_number_auto_generates_for_new_visit(self):
		visit = OPDVisit.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			token_number=None,
			fee=0,
			discount=0,
			total=0,
		)

		self.assertEqual(visit.token_number, 1)

	def test_token_number_increments_daily(self):
		first_visit = OPDVisit.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			token_number=None,
			fee=0,
			discount=0,
			total=0,
		)
		second_visit = OPDVisit.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			token_number=None,
			fee=0,
			discount=0,
			total=0,
		)

		today = timezone.localdate()
		self.assertEqual(first_visit.created_at.date(), today)
		self.assertEqual(second_visit.created_at.date(), today)
		self.assertEqual(first_visit.token_number, 1)
		self.assertEqual(second_visit.token_number, 2)

	def test_admin_token_display_for_existing_record(self):
		visit = OPDVisit.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			token_number=None,
			fee=0,
			discount=0,
			total=0,
		)
		admin_instance = OPDVisitAdmin(OPDVisit, AdminSite())

		self.assertEqual(admin_instance.token_number_display(visit), visit.token_number)

	def test_admin_record_summary_uses_filtered_queryset(self):
		other_doctor = Doctor.objects.create(name="Dr. House", fee=300)
		OPDVisit.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			token_number=None,
			fee=0,
			discount=0,
			total=0,
		)
		OPDVisit.objects.create(
			patient=self.patient,
			doctor=other_doctor,
			token_number=None,
			fee=0,
			discount=0,
			total=0,
		)

		admin_instance = OPDVisitAdmin(OPDVisit, AdminSite())
		summary = admin_instance.get_record_summary(OPDVisit.objects.filter(doctor=self.doctor))

		self.assertEqual(summary["visit_count"], 1)
		self.assertEqual(summary["total_income"], self.doctor.fee)

	def test_admin_changelist_configuration_supports_filtering(self):
		admin_instance = OPDVisitAdmin(OPDVisit, AdminSite())
		self.assertEqual(admin_instance.list_filter, ("doctor", "created_at"))
		self.assertEqual(admin_instance.date_hierarchy, "created_at")
		self.assertIn("patient__name", admin_instance.search_fields)

	def test_changelist_view_injects_record_summary(self):
		admin_instance = OPDVisitAdmin(OPDVisit, AdminSite())
		user = get_user_model().objects.create_superuser(
			username="summaryadmin",
			email="summary@example.com",
			password="password123",
		)
		OPDVisit.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			token_number=None,
			fee=0,
			discount=0,
			total=0,
		)

		request = RequestFactory().get("/admin/opd/opdvisit/")
		request.user = user
		response = admin_instance.changelist_view(request)

		self.assertEqual(response.context_data["record_summary"]["visit_count"], 1)
		self.assertEqual(response.context_data["record_summary"]["total_income"], self.doctor.fee)

	def test_admin_dashboard_context_contains_expected_stats(self):
		yesterday_visit = OPDVisit.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			token_number=None,
			fee=0,
			discount=0,
			total=0,
		)
		OPDVisit.objects.filter(pk=yesterday_visit.pk).update(
			created_at=timezone.now() - timedelta(days=1)
		)

		today_visit = OPDVisit.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			token_number=None,
			fee=0,
			discount=0,
			total=0,
		)

		dashboard = get_admin_dashboard_context()

		self.assertEqual(dashboard["total_patients"], 1)
		self.assertEqual(dashboard["total_doctors"], 1)
		self.assertEqual(dashboard["total_visits"], 2)
		self.assertEqual(dashboard["total_income"], 1000)
		self.assertEqual(dashboard["today_visits"], 1)
		self.assertEqual(dashboard["today_income"], 500)
		self.assertEqual(dashboard["month_income"], dashboard["today_income"])
		self.assertEqual(len(dashboard["last_7_days"]), 7)
		self.assertEqual(dashboard["top_doctors"][0]["doctor__name"], self.doctor.name)
		self.assertEqual(dashboard["recent_visits"][0].pk, today_visit.pk)

	def test_admin_site_each_context_includes_dashboard(self):
		user = get_user_model().objects.create_superuser(
			username="dashboardadmin",
			email="dashboard@example.com",
			password="password123",
		)
		request = RequestFactory().get("/admin/")
		request.user = user

		context = admin.site.each_context(request)

		self.assertIn("dashboard", context)
		self.assertIn("total_income", context["dashboard"])

	def test_admin_panel_branding_is_applied(self):
		self.assertEqual(admin.site.site_header, ADMIN_PANEL_NAME)
		self.assertEqual(admin.site.site_title, ADMIN_PANEL_NAME)
		self.assertEqual(admin.site.index_title, ADMIN_PANEL_NAME)

	def test_response_add_redirects_to_voucher_on_addanother(self):
		visit = OPDVisit.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			token_number=None,
			fee=0,
			discount=0,
			total=0,
		)
		request = RequestFactory().post("/admin/opd/opdvisit/add/", data={"_addanother": "1"})
		request.user = get_user_model().objects.create_superuser(
			username="addanotheradmin",
			email="addanother@example.com",
			password="password123",
		)

		admin_instance = OPDVisitAdmin(OPDVisit, AdminSite())
		response = admin_instance.response_add(request, visit)

		self.assertIsInstance(response, HttpResponseRedirect)
		self.assertIn(reverse("admin:opd_opdvisit_voucher", args=[visit.pk]), response.url)
		self.assertIn(reverse("admin:opd_opdvisit_add"), response.url)

	def test_response_add_redirects_to_voucher_on_markerless_submit(self):
		visit = OPDVisit.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			token_number=None,
			fee=0,
			discount=0,
			total=0,
		)
		request = RequestFactory().post("/admin/opd/opdvisit/add/", data={})
		request.user = get_user_model().objects.create_superuser(
			username="enterfallbackadmin",
			email="enterfallback@example.com",
			password="password123",
		)

		admin_instance = OPDVisitAdmin(OPDVisit, AdminSite())
		response = admin_instance.response_add(request, visit)

		self.assertIsInstance(response, HttpResponseRedirect)
		self.assertIn(reverse("admin:opd_opdvisit_voucher", args=[visit.pk]), response.url)
		self.assertIn(reverse("admin:opd_opdvisit_add"), response.url)

	def test_voucher_view_renders_visit_data(self):
		visit = OPDVisit.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			token_number=None,
			fee=0,
			discount=0,
			total=0,
		)
		request = RequestFactory().get(f"/admin/opd/opdvisit/{visit.pk}/voucher/")
		request.user = get_user_model().objects.create_superuser(
			username="voucheradmin",
			email="voucher@example.com",
			password="password123",
		)

		admin_instance = OPDVisitAdmin(OPDVisit, AdminSite())
		response = admin_instance.voucher_view(request, visit.pk)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context_data["visit"].pk, visit.pk)
		self.assertEqual(response.context_data["next_url"], reverse("admin:opd_opdvisit_add"))
