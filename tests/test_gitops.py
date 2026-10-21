"""Guards for roadmap item 10: multi-arch (amd64 + arm64) release images and GitOps (Argo CD follows k8s/overlays/prod, and the
release workflow proposes the new image digest as a pull request).

None of it can run here (a release needs a tag and a registry, Argo CD needs a cluster): these read the files, cross-check them
against each other and against the resources the overlay really contains, and run the pin script and the architecture check's jq
filter for real. kustomize / jq are used when present and skipped when not.
"""
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
PROD = ROOT / "k8s" / "overlays" / "prod"
ARGO = ROOT / "k8s" / "gitops" / "argocd"

_SPEC = importlib.util.spec_from_file_location("set_image_digests", ROOT / "scripts" / "set_image_digests.py")
pin = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pin)


def release():
    return yaml.safe_load(RELEASE.read_text(encoding="utf-8"))


def steps(job):
    return release()["jobs"][job]["steps"]


def find(job, fragment, key="name"):
    hits = [(i, s) for i, s in enumerate(steps(job)) if fragment in s.get(key, "")]
    assert len(hits) == 1, (fragment, [s.get("name") or s.get("uses") for s in steps(job)])
    return hits[0]


def build_steps(job="publish"):
    return [(i, s) for i, s in enumerate(steps(job)) if s.get("uses", "").startswith("docker/build-push-action@")]


# ----------------------------------------------------------------------------------------------- multi-arch release ----
class MultiArchReleaseTests(SimpleTestCase):
    def test_qemu_is_set_up_for_arm64_only_pinned_by_sha_and_before_buildx(self):
        i, qemu = find("publish", "docker/setup-qemu-action", key="uses")
        self.assertRegex(qemu["uses"], r"^docker/setup-qemu-action@[0-9a-f]{40}$")  # the parser drops the trailing comment
        self.assertRegex(RELEASE.read_text(encoding="utf-8"), r"docker/setup-qemu-action@[0-9a-f]{40} # v\d+\.\d+\.\d+")
        self.assertEqual(qemu["with"]["platforms"], "arm64", "amd64 is native; emulate only what is needed")
        self.assertLess(i, find("publish", "docker/setup-buildx-action", key="uses")[0])

    def test_the_unpinned_binfmt_image_is_flagged_where_it_is_used(self):
        # setup-qemu-action runs docker.io/tonistiigi/binfmt:latest --privileged; until it is pinned by digest the gap must stay visible.
        text = RELEASE.read_text(encoding="utf-8")
        qemu = find("publish", "docker/setup-qemu-action", key="uses")[1]
        pinned = qemu.get("with", {}).get("image", "").startswith("docker.io/tonistiigi/binfmt@sha256:")
        self.assertTrue(pinned or "NOT pinned by digest" in text, "pin the binfmt image or say it is not pinned")

    def test_publish_builds_both_platforms_in_one_index(self):
        _, publish = find("publish", "Publish the multi-arch image")
        self.assertEqual(publish["with"]["platforms"], "linux/amd64,linux/arm64")
        self.assertIs(publish["with"]["push"], True)
        self.assertEqual(publish["with"]["sbom"], True)
        self.assertEqual(publish["with"]["provenance"], "mode=max")

    def test_both_architectures_are_scanned_before_anything_is_published(self):
        scan_amd, build_amd = find("publish", "Scan the amd64 image")[0], find("publish", "Build the linux/amd64 image")
        scan_arm, build_arm = find("publish", "Scan the arm64 image")[0], find("publish", "Build the linux/arm64 image")
        publish = find("publish", "Publish the multi-arch image")[0]
        self.assertEqual(build_amd[1]["with"]["platforms"], "linux/amd64")
        self.assertEqual(build_arm[1]["with"]["platforms"], "linux/arm64")
        for _, b in (build_amd, build_arm):
            self.assertIs(b["with"]["load"], True)
            self.assertIs(b["with"]["push"], False)
        self.assertLess(build_amd[0], scan_amd)
        self.assertLess(build_arm[0], scan_arm)
        self.assertLess(max(scan_amd, scan_arm), publish)
        refs = {steps("publish")[scan_amd]["with"]["image-ref"], steps("publish")[scan_arm]["with"]["image-ref"]}
        self.assertEqual(refs, {"whattocook-${{ matrix.name }}:scan", "whattocook-${{ matrix.name }}:scan-arm64"})

    def test_each_scan_build_has_its_own_cache_scope_and_the_publish_build_reads_both(self):
        amd = find("publish", "Build the linux/amd64 image")[1]["with"]
        arm = find("publish", "Build the linux/arm64 image")[1]["with"]
        publish = find("publish", "Publish the multi-arch image")[1]["with"]
        self.assertNotEqual(amd["cache-to"], arm["cache-to"], "two builds exporting to one scope overwrite each other's index")
        self.assertIn("scope=${{ matrix.name }}-arm64", arm["cache-to"])
        for scope in ("scope=${{ matrix.name }}\n", "scope=${{ matrix.name }}-arm64"):
            self.assertIn(scope, publish["cache-from"] + "\n")

    def test_the_scan_builds_still_bypass_the_cache_for_the_frontend_stage(self):
        for fragment in ("Build the linux/amd64 image", "Build the linux/arm64 image"):
            self.assertEqual(find("publish", fragment)[1]["with"]["no-cache-filters"], "${{ matrix.no-cache-filters }}")
        self.assertNotIn("no-cache-filters", find("publish", "Publish the multi-arch image")[1]["with"])

    def test_the_published_index_is_checked_for_both_architectures_after_publishing(self):
        i, check = find("publish", "Confirm both architectures")
        self.assertGreater(i, find("publish", "Publish the multi-arch image")[0])
        self.assertIn("imagetools inspect", check["run"])
        self.assertIn('select(.os == "linux")', check["run"], "attestation manifests (os unknown) must not count as platforms")
        for arch in ("amd64", "arm64"):
            self.assertIn(f'"{arch}"', check["run"])

    def test_the_architecture_check_rejects_a_single_arch_release(self):
        jq = shutil.which("jq")
        if not jq:
            self.skipTest("jq not installed")
        program = re.search(r"jq -e '([^']+)'", find("publish", "Confirm both architectures")[1]["run"]).group(1)

        def passes(*manifests):
            index = json.dumps({"schemaVersion": 2, "manifests": list(manifests)})
            return subprocess.run([jq, "-e", program], input=index, capture_output=True, text=True).returncode == 0

        def image(arch, os="linux"):
            return {"digest": "sha256:" + arch, "platform": {"architecture": arch, "os": os}}

        attestation = {"digest": "sha256:att", "platform": {"architecture": "unknown", "os": "unknown"}}
        self.assertTrue(passes(image("amd64"), image("arm64"), attestation))
        self.assertFalse(passes(image("amd64"), attestation))
        self.assertFalse(passes(image("arm64"), attestation))
        self.assertFalse(passes(image("amd64"), image("arm64", os="windows")))
        self.assertFalse(passes())

    def test_the_job_has_time_for_an_emulated_build(self):
        self.assertGreaterEqual(release()["jobs"]["publish"]["timeout-minutes"], 45)

    def test_the_spa_is_built_once_on_the_native_builder_and_only_nginx_is_per_architecture(self):
        dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
        # an optional @sha256 pin is fine on either image: the platform rule is what matters here
        self.assertRegex(dockerfile, r"(?m)^FROM --platform=\$BUILDPLATFORM node:\d+-alpine(@sha256:[0-9a-f]{64})? AS build$")
        self.assertRegex(dockerfile, r"(?m)^FROM nginx:alpine(@sha256:[0-9a-f]{64})? AS serve$", "the serving stage must not be pinned to the build platform")


# ------------------------------------------------------------------------------------------------- gitops-bump job ----
class GitopsBumpJobTests(SimpleTestCase):
    def job(self):
        return release()["jobs"]["gitops-bump"]

    def test_it_runs_after_publish_and_only_for_tags(self):
        self.assertEqual(self.job()["needs"], "publish")
        self.assertEqual(self.job()["if"], "startsWith(github.ref, 'refs/tags/v')")

    def test_it_has_least_privilege_and_no_oidc_identity(self):
        self.assertEqual(self.job()["permissions"], {"contents": "write", "pull-requests": "write", "packages": "read"})

    def test_concurrent_releases_queue_instead_of_cancelling_each_other(self):
        self.assertFalse(self.job()["concurrency"]["cancel-in-progress"])

    def test_it_checks_out_main_not_the_tag_and_pushes_with_the_optional_token(self):
        checkout = find("gitops-bump", "actions/checkout", key="uses")[1]
        self.assertEqual(checkout["with"]["ref"], "main")
        self.assertEqual(checkout["with"]["token"], "${{ secrets.GITOPS_TOKEN || github.token }}")

    def test_nothing_is_interpolated_into_a_script_everything_goes_through_env(self):
        for s in steps("gitops-bump"):
            self.assertNotIn("${{", s.get("run", ""), f"{s.get('name')}: use env, not ${{{{ }}}} inside run")

    def test_the_steps_run_in_the_safe_order(self):
        order = [find("gitops-bump", "docker/login-action", key="uses")[0], find("gitops-bump", "cosign-installer", key="uses")[0],
                 find("gitops-bump", "Resolve the released digests")[0], find("gitops-bump", "Pin k8s/overlays/prod")[0],
                 find("gitops-bump", "Open the pull request")[0]]
        self.assertEqual(order, sorted(order))

    def test_a_digest_is_only_written_to_git_after_its_signature_verified_against_this_workflows_identity(self):
        verify = find("gitops-bump", "Resolve the released digests")[1]["run"]
        sign = find("publish", "Sign the image")[1]["run"]
        identity = '--certificate-identity "https://github.com/${GITHUB_WORKFLOW_REF}"'
        issuer = "--certificate-oidc-issuer https://token.actions.githubusercontent.com"
        for text in (verify, sign):
            self.assertIn(identity, text)
            self.assertIn(issuer, text)
        self.assertIn("cosign verify", verify)
        self.assertRegex(verify, r"\^sha256:\[0-9a-f\]\{64\}\$")
        self.assertLess(verify.index("cosign verify"), verify.index("_DIGEST="), "export a digest only after it verified")

    def test_the_pin_step_uses_exactly_the_verified_digests(self):
        run = find("gitops-bump", "Pin k8s/overlays/prod")[1]["run"]
        self.assertIn("scripts/set_image_digests.py", run)
        for flag, var in (("--version", "VERSION"), ("--backend", "BACKEND_DIGEST"), ("--frontend", "FRONTEND_DIGEST")):
            self.assertIn(f'{flag} "${var}"', run)

    def test_it_opens_a_pull_request_and_never_pushes_to_main(self):
        run = find("gitops-bump", "Open the pull request")[1]
        script = run["run"]
        self.assertIn("gh pr create", script)
        self.assertIn('--base main', script)
        self.assertIn('BRANCH="gitops/release-${VERSION}"', script)
        self.assertNotRegex(script, r"git push[^\n]*\bmain\b", "a release must never write to main directly")
        self.assertNotIn("refs/heads/main", script)
        self.assertEqual(run["env"]["GH_TOKEN"], "${{ secrets.GITOPS_TOKEN || github.token }}")
        self.assertRegex(script, r'git commit -m "chore\(release\): deploy \$\{VERSION\}')

    def test_a_rerun_neither_fails_on_no_change_nor_opens_a_second_pull_request(self):
        script = find("gitops-bump", "Open the pull request")[1]["run"]
        self.assertIn("git diff --quiet", script)
        self.assertIn("gh pr view", script)

    def test_the_resolved_tag_is_the_one_the_metadata_action_publishes(self):
        # v1.2.3 -> image tag 1.2.3 (type=semver,pattern={{version}}), so the version is the tag without its v.
        self.assertIn('VERSION="${GITHUB_REF_NAME#v}"', find("gitops-bump", "Resolve the released digests")[1]["run"])
        meta = next(s for s in steps("publish") if s.get("id") == "meta")
        self.assertIn("type=semver,pattern={{version}}", meta["with"]["tags"])


# ----------------------------------------------------------------------------------------------- the pin script ----
BACKEND = "sha256:" + "a" * 64
FRONTEND = "sha256:" + "b" * 64
NAMES = {"whattocook-backend": BACKEND, "whattocook-frontend": FRONTEND}


def overlay_text():
    return (PROD / "kustomization.yaml").read_text(encoding="utf-8")


def images_block(text):
    return yaml.safe_load(text)["images"]


class SetImageDigestsTests(SimpleTestCase):
    def test_both_images_get_the_tag_and_the_digest(self):
        out = images_block(pin.pin_images(overlay_text(), "1.2.3", NAMES))
        self.assertEqual({i["name"]: (i["newTag"], i["digest"]) for i in out}, {n: ("1.2.3", d) for n, d in NAMES.items()})

    def test_the_registry_names_survive(self):
        before = {i["name"]: i["newName"] for i in images_block(overlay_text())}
        after = {i["name"]: i["newName"] for i in images_block(pin.pin_images(overlay_text(), "1.2.3", NAMES))}
        self.assertEqual(before, after)

    def test_everything_outside_the_images_block_is_byte_identical(self):
        original, updated = overlay_text(), pin.pin_images(overlay_text(), "1.2.3", NAMES)

        def outside(text):
            head, _, rest = text.partition("\nimages:\n")
            _, _, tail = rest.partition("\npatches:")
            return head, tail

        self.assertEqual(outside(original), outside(updated))

    def test_running_it_twice_changes_nothing(self):
        once = pin.pin_images(overlay_text(), "1.2.3", NAMES)
        self.assertEqual(pin.pin_images(once, "1.2.3", NAMES), once)

    def test_a_newer_release_replaces_the_old_pin_instead_of_stacking_keys(self):
        once = pin.pin_images(overlay_text(), "1.2.3", NAMES)
        twice = pin.pin_images(once, "1.3.0", {"whattocook-backend": FRONTEND, "whattocook-frontend": BACKEND})
        self.assertEqual(twice.count("newTag:"), 2)
        self.assertEqual(twice.count("digest:"), 2)
        self.assertEqual({i["newTag"] for i in images_block(twice)}, {"1.3.0"})

    def test_prerelease_versions_are_accepted(self):
        self.assertIn("newTag: 2.0.0-rc.1", pin.pin_images(overlay_text(), "2.0.0-rc.1", NAMES))

    def test_bad_input_is_refused_with_a_clear_error(self):
        for version in ("v1.2.3", "1.2", "latest", ""):
            with self.assertRaisesRegex(pin.PinError, "not a release version"):
                pin.pin_images(overlay_text(), version, NAMES)
        for digest in ("sha256:abc", "a" * 64, "sha256:" + "G" * 64, "sha512:" + "a" * 64):
            with self.assertRaisesRegex(pin.PinError, "not a sha256 digest"):
                pin.pin_images(overlay_text(), "1.2.3", {"whattocook-backend": digest})

    def test_an_image_missing_from_the_block_is_an_error_not_a_silent_skip(self):
        with self.assertRaisesRegex(pin.PinError, "not found"):
            pin.pin_images(overlay_text(), "1.2.3", {"whattocook-worker": BACKEND})
        with self.assertRaisesRegex(pin.PinError, "no top-level"):
            pin.pin_images("namespace: x\n", "1.2.3", NAMES)

    def test_the_real_overlay_is_compatible_with_the_script(self):
        self.assertEqual({i["name"] for i in images_block(overlay_text())}, set(NAMES))

    def test_the_command_line_writes_the_file_and_reports_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "kustomization.yaml"
            target.write_text(overlay_text(), encoding="utf-8")
            args = ["--version", "1.2.3", "--backend", BACKEND, "--frontend", FRONTEND, "--file", str(target)]
            self.assertEqual(pin.main(args), 0)
            changed = target.read_text(encoding="utf-8")
            self.assertIn(BACKEND, changed)
            self.assertEqual(pin.main(args), 0)
            self.assertEqual(target.read_text(encoding="utf-8"), changed)

    def test_the_command_line_refuses_bad_input_and_leaves_the_file_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "kustomization.yaml"
            target.write_text(overlay_text(), encoding="utf-8")
            code = pin.main(["--version", "v9", "--backend", BACKEND, "--frontend", FRONTEND, "--file", str(target)])
            self.assertEqual(code, 2)
            self.assertEqual(target.read_text(encoding="utf-8"), overlay_text())

    def test_the_pinned_overlay_renders_as_tag_at_digest(self):
        tool = shutil.which("kustomize")
        cmd = [tool, "build"] if tool else ([shutil.which("kubectl"), "kustomize"] if shutil.which("kubectl") else None)
        if not cmd:
            self.skipTest("neither kustomize nor kubectl installed")
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "k8s"
            shutil.copytree(ROOT / "k8s", copy)
            target = copy / "overlays" / "prod" / "kustomization.yaml"
            target.write_text(pin.pin_images(target.read_text(encoding="utf-8"), "1.2.3", NAMES), encoding="utf-8")
            out = subprocess.run(cmd + [str(copy / "overlays" / "prod")], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(len(re.findall(r"image: ghcr\.io/rezaxr14/whattocook-backend:1\.2\.3@" + re.escape(BACKEND), out.stdout)), 5)
        self.assertEqual(len(re.findall(r"image: ghcr\.io/rezaxr14/whattocook-frontend:1\.2\.3@" + re.escape(FRONTEND), out.stdout)), 1)


# ------------------------------------------------------------------------------------------------ Argo CD manifests ----
def kustomization_resources(directory):
    """Every YAML document reachable through `resources:` (directories recurse into their kustomization.yaml)."""
    docs = []
    config = yaml.safe_load((directory / "kustomization.yaml").read_text(encoding="utf-8"))
    for entry in config.get("resources", []):
        path = (directory / entry).resolve()
        if path.is_dir():
            docs += kustomization_resources(path)
        else:
            docs += [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    return docs


def group_of(doc):
    api = doc["apiVersion"]
    return api.split("/")[0] if "/" in api else ""


CLUSTER_SCOPED = {"Namespace"}


class ArgoManifestTests(SimpleTestCase):
    project = yaml.safe_load((ARGO / "appproject.yaml").read_text(encoding="utf-8"))
    application = yaml.safe_load((ARGO / "application.yaml").read_text(encoding="utf-8"))

    def test_the_application_follows_the_prod_overlay_on_main(self):
        source = self.application["spec"]["source"]
        self.assertEqual(source["path"], "k8s/overlays/prod")
        self.assertEqual(source["targetRevision"], "main")
        self.assertTrue((ROOT / source["path"] / "kustomization.yaml").exists())

    def test_the_application_and_the_project_agree_on_repo_cluster_and_namespace(self):
        spec, project = self.application["spec"], self.project["spec"]
        self.assertEqual(spec["project"], self.project["metadata"]["name"])
        self.assertEqual([spec["source"]["repoURL"]], project["sourceRepos"])
        self.assertEqual([spec["destination"]], [{k: d[k] for k in ("server", "namespace")} for d in project["destinations"]])
        self.assertEqual(spec["destination"]["namespace"], yaml.safe_load((PROD / "kustomization.yaml").read_text())["namespace"])

    def test_the_repo_url_belongs_to_the_same_owner_as_the_images(self):
        owner = re.search(r"github\.com/([^/]+)/", self.application["spec"]["source"]["repoURL"]).group(1)
        for image in yaml.safe_load((PROD / "kustomization.yaml").read_text())["images"]:
            self.assertTrue(image["newName"].startswith(f"ghcr.io/{owner}/"), image)

    def test_sync_is_automated_with_prune_and_self_heal(self):
        automated = self.application["spec"]["syncPolicy"]["automated"]
        self.assertIs(automated["prune"], True)
        self.assertIs(automated["selfHeal"], True)

    def test_deleting_the_application_does_not_cascade_to_the_database(self):
        self.assertNotIn("finalizers", self.application["metadata"], "resources-finalizer would delete every workload and volume with the Application")

    def test_the_project_allows_exactly_the_kinds_the_overlay_contains_and_never_a_secret_or_a_wildcard(self):
        docs = kustomization_resources(PROD)
        namespaced = {(group_of(d), d["kind"]) for d in docs if d["kind"] not in CLUSTER_SCOPED}
        cluster = {(group_of(d), d["kind"]) for d in docs if d["kind"] in CLUSTER_SCOPED}
        spec = self.project["spec"]
        self.assertEqual({(e["group"], e["kind"]) for e in spec["namespaceResourceWhitelist"]}, namespaced)
        self.assertEqual({(e["group"], e["kind"]) for e in spec["clusterResourceWhitelist"]}, cluster)
        for entry in spec["namespaceResourceWhitelist"] + spec["clusterResourceWhitelist"]:
            self.assertNotIn("*", (entry["group"], entry["kind"]))
            self.assertNotEqual(entry["kind"], "Secret", "the secret is created out of band; Argo CD must not manage it")

    def test_every_pvc_in_git_opts_out_of_pruning(self):
        pvcs = [d for d in kustomization_resources(PROD) if d["kind"] == "PersistentVolumeClaim"]
        self.assertGreaterEqual(len(pvcs), 2)
        for pvc in pvcs:
            self.assertEqual(pvc["metadata"].get("annotations", {}).get("argocd.argoproj.io/sync-options"), "Prune=false", pvc["metadata"]["name"])

    def test_the_gitops_directory_is_not_part_of_any_kustomization(self):
        for kustomization in (ROOT / "k8s").rglob("kustomization.yaml"):
            entries = yaml.safe_load(kustomization.read_text(encoding="utf-8")).get("resources", [])
            self.assertFalse([e for e in entries if "gitops" in e], f"{kustomization} would deploy the Argo CD manifests as workloads")
