"""Guards for the fixes that keep the image scan (.github/actions/scan-image) green without .trivyignore entries.

The base images are pinned by digest (name:tag@sha256:..., the multi-arch index), so a rebuild cannot change them silently;
new fixable HIGH/CRITICAL findings still appear (Alpine publishes fixes before nginx rebuilds, and a pinned Python base
only moves when Dependabot moves its digest). The answer is to take the fix (upgrade the package or the digest), not to
ignore it; these tests keep that answer from being edited away. The scan itself runs in CI (it needs Docker and the Trivy
database).
"""
import re
from pathlib import Path

import yaml
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DOCKERFILE = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
DOCKERFILES = ("Dockerfile", "frontend/Dockerfile")
FROM_LINE = re.compile(r"(?m)^FROM\s+(?:--platform=\S+\s+)?(?P<ref>\S+)(?:\s+AS\s+(?P<alias>\S+))?\s*$")
# name:tag@sha256:<64 hex>. The tag is kept on purpose: Dependabot needs it to propose the next digest, and a reader needs it to know what this is.
PINNED_REF = re.compile(r"^[a-z0-9][a-z0-9./_-]*:[\w][\w.-]*@sha256:[0-9a-f]{64}$")
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
        self.assertRegex(header, r"^nginx:alpine@sha256:[0-9a-f]{64} AS serve$")
        instructions = [line for line in body.splitlines() if re.match(r"(RUN|COPY|ADD) ", line)]
        self.assertEqual(instructions[0], "RUN apk upgrade --no-cache", "upgrade first, so everything after it sits on the fixed packages")

    def test_the_scan_builds_rebuild_that_stage_so_a_cached_layer_cannot_hide_a_newer_fix(self):
        for wf, job in (("security.yml", "image-scan"), ("release.yml", "publish")):
            with self.subTest(workflow=wf):
                m = matrix(wf, job)
                self.assertEqual(m["frontend"]["no-cache-filters"], "serve")
                self.assertEqual(m["backend"]["no-cache-filters"], "", "the backend Dockerfile has no such stage")
                scans = [b for b in build_steps(wf, job) if not b["with"]["push"]]
                self.assertTrue(scans, "no scan build found")
                for scan_build in scans:  # release.yml scans amd64 and arm64
                    self.assertEqual(scan_build["with"]["no-cache-filters"], "${{ matrix.no-cache-filters }}")

    def test_the_stage_the_workflows_name_exists_in_the_dockerfile(self):
        stage = matrix("security.yml", "image-scan")["frontend"]["no-cache-filters"]
        self.assertIn(f" AS {stage}\n", FRONTEND_DOCKERFILE)

    def test_the_published_image_is_not_rebuilt_fresh_it_is_what_was_scanned(self):
        builds = build_steps("release.yml", "publish")
        scans = [b for b in builds if not b["with"]["push"]]
        publishes = [b for b in builds if b["with"]["push"]]
        self.assertGreaterEqual(len(scans), 1)
        self.assertEqual(len(publishes), 1, "exactly one build publishes")
        self.assertNotIn("no-cache-filters", publishes[0]["with"], "a second fresh build could differ from the image that passed the scan")


class BackendImageTests(SimpleTestCase):
    def pinned_setuptools(self):
        m = re.search(r"(?m)^setuptools~=(\d+)\.(\d+)\.(\d+)\s*$", REQUIREMENTS)
        self.assertIsNotNone(m, "requirements.txt must pin setuptools (the base image's own copy carries flagged vendored packages)")
        return tuple(int(x) for x in m.groups())

    def test_setuptools_is_pinned_past_the_flagged_vendored_packages_and_the_advisory(self):
        # 79.x-80.9 vendor jaraco.context 5.3.0 / wheel 0.45.1 (Trivy HIGH); 80.10.2 fixed those but is itself affected by
        # CVE-2026-59890, fixed in 83.0.0 (pip-audit would fail on it).
        self.assertGreaterEqual(self.pinned_setuptools(), (83, 0, 0))

    def test_djangorestframework_is_pinned_at_or_past_the_release_that_fixes_three_advisories(self):
        # 3.17.2 and earlier: GHSA-33wh-fxxf-88vv, GHSA-3547-9m27-7rxg, GHSA-xw6w-gcfp-cf8m (Trivy HIGH, pip-audit fails), fixed in 3.18.2.
        # `~=3.17.2` still allowed 3.17.x forever, so the pin has to name the fixed minor.
        m = re.search(r"(?m)^djangorestframework~=(\d+)\.(\d+)\.(\d+)\s*$", REQUIREMENTS)
        self.assertIsNotNone(m, "requirements.txt must pin djangorestframework with ~=X.Y.Z")
        self.assertGreaterEqual(tuple(int(x) for x in m.groups()), (3, 18, 2))

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


class BaseImagePinTests(SimpleTestCase):
    @staticmethod
    def external_bases():
        """(dockerfile, image reference) for every FROM that names a registry image (not a stage of the same file, not scratch)."""
        found = []
        for name in DOCKERFILES:
            stages = set()
            for m in FROM_LINE.finditer((ROOT / name).read_text(encoding="utf-8")):
                if m["ref"] != "scratch" and m["ref"] not in stages:
                    found.append((name, m["ref"]))
                if m["alias"]:
                    stages.add(m["alias"])
        return found

    def test_the_parser_finds_the_three_base_images_so_the_checks_below_cannot_pass_on_nothing(self):
        self.assertEqual(sorted(ref.split(":")[0] for _, ref in self.external_bases()), ["nginx", "node", "python"])

    def test_every_external_base_image_is_pinned_by_digest_and_keeps_its_tag(self):
        for name, ref in self.external_bases():
            with self.subTest(dockerfile=name, ref=ref):
                self.assertRegex(ref, PINNED_REF, f"{name}: pin as image:tag@sha256:<digest of the multi-arch index>")
