"""Sync system flow templates from seed data into the FlowTemplate table.

Usage:
    python manage.py seed_flow_templates
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from api.flow_seed_data import FLOW_STEP_TEMPLATES, MAIN_MENU_FLOWS
from api.models import FlowTemplate


class Command(BaseCommand):
    help = "Load or refresh system flow templates in the database."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for i, flow in enumerate(MAIN_MENU_FLOWS):
            step_config = FLOW_STEP_TEMPLATES.get(flow["key"], [])
            obj, was_created = FlowTemplate.objects.update_or_create(
                key=flow["key"],
                defaults={
                    "default_option_id": flow["id"],
                    "label": flow["label"],
                    "category": flow.get("category", FlowTemplate.Category.BOOKING),
                    "description": flow.get("description", ""),
                    "submit_url": flow.get("submit_url", ""),
                    "steps": flow.get("steps", []),
                    "step_config": [dict(step) for step in step_config],
                    "is_active": True,
                    "sort_order": i,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Flow templates synced: {created} created, {updated} updated."
            )
        )
