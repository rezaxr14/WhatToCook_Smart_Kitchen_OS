"""Supply-chain guards for .github/: pinned actions, a pinned scanner, and a release that scans, attests and signs.

These read the workflow files only (no network); the release itself can only be proven by running it
(workflow_dispatch on release.yml), which is noted in the README.
"""
import re
from pathlib import Path

import yaml
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent
GH = ROOT / ".github"
WORKFLOWS = sorted((GH / "workflows").glob("*.yml"))
ACTIONS = sorted((GH / "actions").glob("*/action.yml"))
USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<ref>\S+)(?P<rest>.*)$")


def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def steps(workflow, job):
    return load(GH / "workflows" / workflow)["jobs"][job]["steps"]


def step_index(step_list, predicate):
    return next(i for i, s in enumerate(step_list) if predicate(s))


class PinnedActionTests(SimpleTestCase):
    def test_there_are_workflows_to_check(self):
        self.assertGreaterEqual(len(WORKFLOWS), 6)
        self.assertTrue(ACTIONS)

    def test_every_action_is_pinned_to_a_full_commit_sha_with_a_version_comment(self):
        problems = []
        for path in WORKFLOWS + ACTIONS:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                m = USES.match(line)
                if not m or m["ref"].startswith("./"):  # local actions live in this repo
                    continue
                where = f"{path.relative_to(ROOT)}:{number}"
                if not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", m["ref"]):
                    problems.append(f"{where}: {m['ref']} is not pinned to a 40-char commit SHA")
                elif not re.fullmatch(r"\s+#\s+v\d+\.\d+\.\d+\s*", m["rest"]):
                    problems.append(f"{where}: {m['ref']} needs a trailing '# vX.Y.Z' comment (Dependabot keeps it in sync)")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_local_actions_that_are_referenced_exist(self):
        for path in WORKFLOWS:
            for line in path.read_text(encoding="utf-8").splitlines():
                m = USES.match(line)
                if m and m["ref"].startswith("./"):
                    self.assertTrue((ROOT / m["ref"] / "action.yml").exists(), f"{path.name}: {m['ref']}")

    def test_dependabot_leaves_node_majors_to_a_deliberate_bump(self):
        updates = load(GH / "dependabot.yml")["updates"]
        major = ["version-update:semver-major"]
        docker = next(u for u in updates if u["package-ecosystem"] == "docker" and u["directory"] == "/frontend")
        npm = next(u for u in updates if u["package-ecosystem"] == "npm")
        self.assertIn({"dependency-name": "node", "update-types": major}, docker["ignore"])
        self.assertIn({"dependency-name": "@types/node", "update-types": major}, npm["ignore"])
        root_docker = next(u for u in updates if u["package-ecosystem"] == "docker" and u["directory"] == "/")
        self.assertNotIn("node", [i["dependency-name"] for i in root_docker.get("ignore", [])], "the Python image is not Node")

    def test_dependabot_watches_the_composite_action_directory(self):
        updates = load(GH / "dependabot.yml")["updates"]
        gha = next(u for u in updates if u["package-ecosystem"] == "github-actions")
        self.assertIn("/.github/actions/*", gha["directories"])
        self.assertIn("/", gha["directories"])


class ScannerTests(SimpleTestCase):
    def setUp(self):
        self.action = load(GH / "actions" / "scan-image" / "action.yml")
        self.trivy = next(s for s in self.action["runs"]["steps"] if "trivy-action" in s.get("uses", ""))["with"]

    def test_scanner_version_is_pinned_explicitly(self):
        # trivy-action downloads the scanner at run time and otherwise uses its own default (a different version).
        self.assertRegex(self.trivy["version"], r"^v\d+\.\d+\.\d+$")

    def test_policy_fails_the_build_on_fixable_high_and_critical(self):
        self.assertEqual(self.trivy["exit-code"], "1")
        self.assertEqual(set(self.trivy["severity"].split(",")), {"HIGH", "CRITICAL"})
        self.assertEqual(self.trivy["ignore-unfixed"], "true")

    def test_ignore_file_exists_and_every_entry_is_justified(self):
        lines = (ROOT / self.trivy["trivyignores"]).read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.strip() and not line.startswith("#"):
                self.assertTrue(lines[i - 1].startswith("#"), f"{line!r} needs a comment line above it saying why and until when")

    def test_pr_scan_runs_the_same_shared_action_on_both_images(self):
        scan_job = load(GH / "workflows" / "security.yml")["jobs"]["image-scan"]
        self.assertEqual({m["name"] for m in scan_job["strategy"]["matrix"]["include"]}, {"backend", "frontend"})
        self.assertTrue(any(s.get("uses") == "./.github/actions/scan-image" for s in scan_job["steps"]))
        build = next(s for s in scan_job["steps"] if "build-push-action" in s.get("uses", ""))
        self.assertIs(build["with"]["push"], False)  # a PR must never publish an image

    def test_dependency_audit_includes_dev_dependencies(self):
        audit = next(s for s in steps("security.yml", "dependency-audit") if "npm audit" in s.get("run", ""))
        self.assertNotIn("--omit=dev", audit["run"])


class ReleaseTests(SimpleTestCase):
    def setUp(self):
        self.workflow = load(GH / "workflows" / "release.yml")
        self.steps = self.workflow["jobs"]["publish"]["steps"]

    def _is(self, fragment):
        return lambda s: fragment in s.get("uses", "") or fragment in s.get("run", "") or fragment in s.get("name", "")

    def test_oidc_token_is_available_for_keyless_signing_and_nothing_broader_than_needed(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read", "packages": "write", "id-token": "write"})

    def test_the_image_is_scanned_before_anything_is_published(self):
        scan = step_index(self.steps, lambda s: s.get("uses") == "./.github/actions/scan-image")
        publish = step_index(self.steps, lambda s: s.get("id") == "build")
        local = step_index(self.steps, lambda s: "build-push-action" in s.get("uses", "") and s["with"].get("push") is False)
        self.assertLess(local, scan)
        self.assertLess(scan, publish)
        self.assertIs(self.steps[local]["with"]["load"], True)
        self.assertIs(self.steps[publish]["with"]["push"], True)

    def test_published_image_carries_an_sbom_and_provenance(self):
        publish = next(s for s in self.steps if s.get("id") == "build")["with"]
        self.assertIs(publish["sbom"], True)
        self.assertEqual(publish["provenance"], "mode=max")

    def test_cosign_tool_is_pinned_not_just_the_installer(self):
        installer = next(s for s in self.steps if "cosign-installer" in s.get("uses", ""))
        self.assertRegex(installer["with"]["cosign-release"], r"^v\d+\.\d+\.\d+$")

    def test_signing_is_keyless_by_digest_and_verified_against_this_workflows_identity(self):
        sign = next(s for s in self.steps if "cosign sign" in s.get("run", ""))
        self.assertIn('cosign sign --yes "${IMAGE}@${DIGEST}"', sign["run"])  # a digest, never a tag
        self.assertNotIn("--key", sign["run"])  # keyless: no long-lived key to leak
        self.assertIn("cosign verify", sign["run"])
        self.assertIn("--certificate-identity", sign["run"])
        self.assertIn("${GITHUB_WORKFLOW_REF}", sign["run"])
        self.assertIn("--certificate-oidc-issuer https://token.actions.githubusercontent.com", sign["run"])
        self.assertEqual(sign["env"]["DIGEST"], "${{ steps.build.outputs.digest }}")

    def test_signing_happens_after_publishing_and_attestations_are_checked_last(self):
        publish = step_index(self.steps, lambda s: s.get("id") == "build")
        sign = step_index(self.steps, lambda s: "cosign sign" in s.get("run", ""))
        attest = step_index(self.steps, lambda s: "attestation-manifest" in s.get("run", ""))
        self.assertLess(publish, sign)
        self.assertLess(sign, attest)
        self.assertIn("spdxVersion", self.steps[attest]["run"])


class DownloadedToolTests(SimpleTestCase):
    """A tool fetched from `releases/latest` changes under CI without a commit of ours (and runs unverified). Pin a release and its sha256."""

    def test_no_workflow_or_action_downloads_releases_latest(self):
        for path in WORKFLOWS + ACTIONS:
            with self.subTest(path=path.name):
                self.assertNotIn("releases/latest", path.read_text(encoding="utf-8"))

    def test_kubeconform_is_pinned_to_a_release_and_verified_before_it_is_unpacked(self):
        step = next(s for s in steps("ci.yml", "deploy-config") if s.get("name", "").startswith("Validate against Kubernetes"))
        self.assertRegex(step["env"]["KUBECONFORM_VERSION"], r"^v\d+\.\d+\.\d+$")
        self.assertRegex(step["env"]["KUBECONFORM_SHA256"], r"^[0-9a-f]{64}$")
        run = step["run"]
        self.assertIn("${KUBECONFORM_VERSION}", run)
        self.assertIn("${KUBECONFORM_SHA256}", run)
        self.assertIn("--max-time", run)
        self.assertNotRegex(run, r"curl[^\n]*\|\s*tar", "download to a file, verify it, then unpack: never pipe an unverified download into tar")
        self.assertLess(run.index("sha256sum -c"), run.index("tar -xzf"), "verify before unpacking")
        self.assertLess(run.index("tar -xzf"), run.index("./kubeconform -strict"))

