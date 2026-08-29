"""API URL routes (mounted under /api/)."""
from django.urls import path

from . import auth_views, views

urlpatterns = [
    # Auth (tenant signup / login)
    path("auth/signup", auth_views.signup),
    path("auth/login", auth_views.login),
    path("auth/me", auth_views.me),
    path("auth/logout", auth_views.logout),
    # Tenant design / configuration
    path("tenants", views.tenants),
    path("tenants/<slug:slug>/design", views.tenant_design),
    path("tenants/<slug:slug>/design/upload", views.upload_design_image),
    path("tenants/<slug:slug>/flows/reset", views.reset_tenant_flows),
    path("tenants/<slug:slug>/flows/create", views.create_tenant_flow),
    path("tenants/<slug:slug>/flows/<int:option_id>", views.delete_tenant_flow),
    # Flow catalog (shared with frontend)
    path("flows", views.flows_list),
    # Catalog
    path("countries", views.countries),
    path("branches", views.branches),
    path("departments", views.departments),
    path("doctors", views.doctors),
    path("surgeries", views.surgeries),
    path("time-slots", views.time_slots),
    # Appointments
    path("patients", views.patients_by_phone),
    path("appointments", views.appointments_by_phone),
    path("appointments/submit", views.submit_appointment),
    path("appointments/cancel", views.cancel_appointment),
    path("appointments/reschedule", views.reschedule_appointment),
    # AI
    path("ai/detect-intent", views.detect_intent_view),
    path("ai/chat", views.chat),
    path("ai/transcribe", views.transcribe),
    # HIMS backend integration (admin)
    path("settings/hims", views.hims_backend_settings),
    path("settings/hims/tokens", views.hims_tokens),
    path("settings/hims/tokens/<int:token_id>", views.hims_token_detail),
    path("settings/hims/generate-token", views.hims_generate_token),
    # Admin dashboard / appointments
    path("admin/dashboard", views.admin_dashboard),
    path("admin/appointments", views.admin_appointments),
    path("admin/doctors", views.admin_doctors),
]
