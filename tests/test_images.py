"""Guards for the fixes that keep the image scan (.github/actions/scan-image) green without .trivyignore entries.

Both base images float on tags (nginx:alpine, python:3.11-slim), so new fixable HIGH/CRITICAL findings appear without any
change of ours. The answer is to take the fix (upgrade the package), not to ignore it; these tests keep that answer from
being edited away. The scan itself runs in CI (it needs Docker and the Trivy database).
"""
import re
from pathlib import Path

import yaml
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DOCKERFILE = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
REQUIREMENTS = (ROOT / "requirements.txt").read_text(encoding="utf-8")


def workflow(name):
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


def build_steps(name, job):
    return [s for s in workflow(name)["jobs"][job]["steps"] if s.get("uses", "").startswith("docker/build-push-action@")]


def matrix(name, job):
    return {m["name"]: m for m in workflow(name)["jobs"][job]["strategy"]["matrix"]["include"]}


class FrontendImageTests(SimpleTestCase):
    def final_stage(self):
        parts = re.split(r"(?m)^FROM ", FRONTEND_DOCKERFILE)[1:]
        header, _, body = parts[-1].partition("\n")
        return header.strip(), body

    def test_the_serving_stage_is_named_and_upgrades_os_packages_before_anything_else(self):
        header, body = self.final_stage()
        self.assertEqual(header, "nginx:alpine AS serve")
        instructions = [line for line in body.splitlines() if re.match(r"(RUN|COPY|ADD) ", line)]
        self.assertEqual(instructions[0], "RUN apk upgrade --no-cache", "upgrade first, so everything after it sits on the fixed packages")

    def test_the_scan_builds_rebuild_that_stage_so_a_cached_layer_cannot_hide_a_newer_fix(self):
        for wf, job in (("security.yml", "image-scan"), ("release.yml", "publish")):
            with self.subTest(workflow=wf):
                m = matrix(wf, job)
                self.assertEqual(m["frontend"]["no-cache-filters"], "serve")
                self.assertEqual(m["backend"]["no-cache-filters"], "", "the backend Dockerfile has no such stage")
                scan_build = build_steps(wf, job)[0]
                self.assertEqual(scan_build["with"]["no-cache-filters"], "${{ matrix.no-cache-filters }}")

    def test_the_stage_the_workflows_name_exists_in_the_dockerfile(self):
        stage = matrix("security.yml", "image-scan")["frontend"]["no-cache-filters"]
        self.assertIn(f" AS {stage}\n", FRONTEND_DOCKERFILE)

    def test_the_published_image_is_not_rebuilt_fresh_it_is_what_was_scanned(self):
        scan_build, publish = build_steps("release.yml", "publish")
        self.assertFalse(scan_build["with"]["push"])
        self.assertTrue(publish["with"]["push"])
        self.assertNotIn("no-cache-filters", publish["with"], "a second fresh build could differ from the image that passed the scan")


class BackendImageTests(SimpleTestCase):
    def pinned_setuptools(self):
        m = re.search(r"(?m)^setuptools~=(\d+)\.(\d+)\.(\d+)\s*$", REQUIREMENTS)
        self.assertIsNotNone(m, "requirements.txt must pin setuptools (the base image's own copy carries flagged vendored packages)")
        return tuple(int(x) for x in m.groups())

    def test_setuptools_is_pinned_past_the_flagged_vendored_packages_and_the_advisory(self):
        # 79.x-80.9 vendor jaraco.context 5.3.0 / wheel 0.45.1 (Trivy HIGH); 80.10.2 fixed those but is itself affected by
        # CVE-2026-59890, fixed in 83.0.0 (pip-audit would fail on it).
        self.assertGreaterEqual(self.pinned_setuptools(), (83, 0, 0))

    def test_nothing_of_ours_needs_pkg_resources_because_setuptools_82_and_later_do_not_ship_it(self):
        self_path = Path(__file__).resolve()
        pattern = re.compile(r"(?m)^\s*(?:import|from)\s+pkg_resources\b")
        offenders = [
            str(p.relative_to(ROOT))
            for folder in ("GetFood", "WhatToCook", "tests", "scripts")
            for p in (ROOT / folder).rglob("*.py")
            if p.resolve() != self_path and pattern.search(p.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [])
