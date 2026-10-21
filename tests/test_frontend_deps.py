"""Guards for the React Router 6 -> 7 migration (roadmap item 11). The browser behaviour is proven by e2e / e2e-csp in CI;
these keep the things that made the migration safe from regressing, and read the lockfile so the *resolved* version is checked.
"""
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
PACKAGE = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
LOCK = json.loads((FRONTEND / "package-lock.json").read_text(encoding="utf-8"))["packages"]


def version(text):
    return tuple(int(x) for x in re.findall(r"\d+", text)[:3])


def source_files():
    for folder in ("src", "e2e", "e2e-csp", "e2e-visual"):
        base = FRONTEND / folder
        if base.exists():
            yield from (p for ext in ("*.ts", "*.tsx") for p in base.rglob(ext))
    yield FRONTEND / "vite.config.ts"


class ReactRouterVersionTests(SimpleTestCase):
    def test_the_declared_range_is_v7_at_or_after_the_fix_and_below_v8(self):
        # 7.18.0 is the first release outside the vulnerable range (<= 7.17.0: open redirect GHSA-wrjc-x8rr-h8h6,
        # GHSA-337j-9hxr-rhxg). v8 needs React >= 19.2.7 and Node >= 22.22, this app is on React 18 / Node 20.
        declared = PACKAGE["dependencies"]["react-router"]
        self.assertTrue(declared.startswith("^7."), declared)
        self.assertGreaterEqual(version(declared), (7, 18, 0))

    def test_the_resolved_version_in_the_lockfile_is_fixed(self):
        resolved = version(LOCK["node_modules/react-router"]["version"])
        self.assertGreaterEqual(resolved, (7, 18, 0))
        self.assertLess(resolved, (8, 0, 0))

    def test_react_router_dom_and_the_v6_core_are_gone(self):
        for section in ("dependencies", "devDependencies"):
            self.assertNotIn("react-router-dom", PACKAGE.get(section, {}))
        self.assertNotIn("node_modules/react-router-dom", LOCK)
        self.assertNotIn("node_modules/@remix-run/router", LOCK)

    def test_nothing_imports_react_router_dom(self):
        offenders = [str(p.relative_to(ROOT)) for p in source_files() if "react-router-dom" in p.read_text(encoding="utf-8")]
        self.assertEqual(offenders, [])

    def test_node_is_new_enough_for_the_router_everywhere_it_is_pinned(self):
        needed = version(LOCK["node_modules/react-router"]["engines"]["node"])[0]
        pins = {"frontend/Dockerfile": [int(m) for m in re.findall(r"(?m)^FROM (?:--platform=\S+ )?node:(\d+)", (FRONTEND / "Dockerfile").read_text())]}
        for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
            found = [int(m) for m in re.findall(r"node-version:\s*(\d+)", wf.read_text())]
            if found:
                pins[f".github/workflows/{wf.name}"] = found
        self.assertIn("frontend/Dockerfile", pins)
        self.assertTrue(pins["frontend/Dockerfile"], "no FROM node: line found")
        for where, majors in pins.items():
            for major in majors:
                self.assertGreaterEqual(major, needed, f"{where} uses Node {major}; react-router needs >= {needed}")


class ReactRouterBehaviourTests(SimpleTestCase):
    def test_the_vendor_chunk_names_v7s_packages_and_not_the_removed_ones(self):
        config = (FRONTEND / "vite.config.ts").read_text(encoding="utf-8")
        line = next(l for l in config.splitlines() if "vendor-react" in l)
        for name in ("react-router", "cookie", "set-cookie-parser"):  # react-router 7's own dependencies
            self.assertIn(f"'{name}'", line)
        for gone in ("react-router-dom", "@remix-run/router"):
            self.assertNotIn(gone, config)

    def test_router_updates_are_not_wrapped_in_start_transition(self):
        # v7 does that by default, which keeps the old page on screen (no spinner) while a lazy route chunk loads.
        app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn("<Router useTransitions={false}>", app)
        self.assertIn("lazy(", app, "if routes are no longer lazy, revisit useTransitions")
