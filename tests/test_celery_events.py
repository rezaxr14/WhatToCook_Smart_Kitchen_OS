"""Flower (and so the Grafana Celery panels) is fed entirely by Celery *events*, which workers only emit when
asked. Without these settings Flower's flower_events_total / runtime histogram / worker_online stay empty."""
import os
from unittest.mock import patch

from django.test import SimpleTestCase

from WhatToCook.celery import app


class CeleryEventsTests(SimpleTestCase):
    def test_workers_emit_task_events_for_flower(self):
        self.assertTrue(app.conf.worker_send_task_events)

    def test_task_sent_events_are_enabled_so_publishing_is_visible_too(self):
        self.assertTrue(app.conf.task_send_sent_event)

    def test_events_can_be_switched_off_by_env(self):
        # The settings module reads CELERY_SEND_EVENTS at import time, so re-evaluate its helper directly.
        from WhatToCook import settings

        with patch.dict(os.environ, {"CELERY_SEND_EVENTS": "false"}):
            self.assertFalse(settings._env_bool("CELERY_SEND_EVENTS", "true"))
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CELERY_SEND_EVENTS", None)
            self.assertTrue(settings._env_bool("CELERY_SEND_EVENTS", "true"))
