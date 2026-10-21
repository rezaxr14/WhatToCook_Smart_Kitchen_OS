#!/usr/bin/env python3
"""Pin the images of the prod overlay to one release: `newTag` (readable) plus `digest` (immutable). Standard library only.

    python3 scripts/set_image_digests.py --version 1.2.3 --backend sha256:<64 hex> --frontend sha256:<64 hex>
            [--file k8s/overlays/prod/kustomization.yaml]

kustomize renders that as `ghcr.io/<owner>/whattocook-backend:1.2.3@sha256:...` (checked against kustomize 5.8.3: tag and digest
together are both kept). The container runtime resolves by digest, so a moved tag cannot change what runs; the tag is for humans
and for `kubectl get`. Only the two whattocook entries of the `images:` block are touched, every other byte of the file stays.
The release workflow (.github/workflows/release.yml, job gitops-bump) calls this with digests it has just verified with cosign
and opens a pull request: merging that pull request is the deploy, Argo CD (k8s/gitops/argocd) does the rest.
"""
import argparse
import re
import sys
from pathlib import Path

DEFAULT_FILE = "k8s/overlays/prod/kustomization.yaml"
IMAGE_NAMES = {"backend": "whattocook-backend", "frontend": "whattocook-frontend"}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ENTRY_RE = re.compile(r"^  - name: (\S+)\s*$")
KEY_RE = re.compile(r"^    (\w+):")


class PinError(ValueError):
    pass


def pin_images(text, version, digests):
    """Return `text` with the images of `digests` ({kustomize image name: digest}) pinned to `version`."""
    if not VERSION_RE.match(version):
        raise PinError(f"not a release version: {version!r} (expected 1.2.3 or 1.2.3-rc.1, without the leading v)")
    for name, digest in digests.items():
        if not DIGEST_RE.match(digest):
            raise PinError(f"not a sha256 digest for {name}: {digest!r}")
    lines = text.split("\n")
    try:
        start = lines.index("images:")
    except ValueError:
        raise PinError("no top-level `images:` block in the kustomization") from None
    end = start + 1
    while end < len(lines) and (lines[end] == "" or lines[end].startswith((" ", "#"))):
        end += 1
    block = lines[start + 1:end]

    out, i, seen = [], 0, set()
    while i < len(block):
        entry = ENTRY_RE.match(block[i])
        if not entry:
            out.append(block[i])
            i += 1
            continue
        j = i + 1
        while j < len(block) and not ENTRY_RE.match(block[j]) and (block[j].startswith("    ") or block[j] == ""):
            j += 1
        body = block[i:j]
        name = entry.group(1)
        if name in digests:
            seen.add(name)
            trailing = []
            while body and body[-1] == "":
                trailing.append(body.pop())
            kept = [body[0]] + [ln for ln in body[1:] if not (KEY_RE.match(ln) and KEY_RE.match(ln).group(1) in ("newTag", "digest"))]
            kept += [f"    newTag: {version}", f"    digest: {digests[name]}"] + trailing
            body = kept
        out.extend(body)
        i = j
    missing = set(digests) - seen
    if missing:
        raise PinError(f"image(s) not found in the images: block: {', '.join(sorted(missing))}")
    return "\n".join(lines[:start + 1] + out + lines[end:])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--version", required=True)
    parser.add_argument("--backend", required=True, help="sha256:<64 hex> of the backend image")
    parser.add_argument("--frontend", required=True, help="sha256:<64 hex> of the frontend image")
    parser.add_argument("--file", default=DEFAULT_FILE)
    args = parser.parse_args(argv)
    path = Path(args.file)
    original = path.read_text(encoding="utf-8")
    try:
        updated = pin_images(original, args.version, {IMAGE_NAMES["backend"]: args.backend, IMAGE_NAMES["frontend"]: args.frontend})
    except PinError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    if updated == original:
        print(f"{path}: already pinned to {args.version}, nothing to change")
        return 0
    path.write_text(updated, encoding="utf-8")
    print(f"{path}: pinned to {args.version} (backend {args.backend[:19]}..., frontend {args.frontend[:19]}...)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
