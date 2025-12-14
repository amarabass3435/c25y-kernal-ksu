#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def ensure_line_in_file(path: Path, line: str, after_regex: Optional[str] = None) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if line in text:
        return

    if after_regex:
        m = re.search(after_regex, text, flags=re.MULTILINE)
        if m:
            insert_at = m.end(0)
            if insert_at < len(text) and text[insert_at] != "\n":
                # If regex ended mid-line, move to end-of-line
                insert_at = text.find("\n", insert_at)
                if insert_at == -1:
                    insert_at = len(text)
            insert = ("\n" if (insert_at > 0 and text[insert_at - 1] != "\n") else "") + line + "\n"
            text = text[:insert_at] + insert + text[insert_at:]
            path.write_text(text, encoding="utf-8", newline="\n")
            return

    # Fallback: append
    if not text.endswith("\n"):
        text += "\n"
    text += line + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def set_defconfig_symbol(defconfig: Path, sym: str, value: str) -> None:
    # value should be 'y' or 'm' or a literal value.
    text = defconfig.read_text(encoding="utf-8", errors="replace")

    # Remove "# CONFIG_FOO is not set"
    text = re.sub(rf"^#\s*CONFIG_{re.escape(sym)}\s+is\s+not\s+set\s*$\n?", "", text, flags=re.MULTILINE)

    line = f"CONFIG_{sym}={value}"
    if re.search(rf"^CONFIG_{re.escape(sym)}=", text, flags=re.MULTILINE):
        text = re.sub(rf"^CONFIG_{re.escape(sym)}=.*$", line, text, flags=re.MULTILINE)
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += line + "\n"

    defconfig.write_text(text, encoding="utf-8", newline="\n")


def copy_kernelsu_sources(ksu_repo: Path, kernel_repo: Path) -> None:
    # KernelSU v0.9.5 layout: KernelSU/kernel/*
    src = ksu_repo / "kernel"
    if not src.is_dir():
        raise SystemExit(f"KernelSU sources not found at: {src}")

    dst = kernel_repo / "drivers" / "kernelsu"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    # Normalize Kconfig LF (prevents Kconfig parser warnings)
    kconfig = dst / "Kconfig"
    if kconfig.exists():
        kconfig.write_text(kconfig.read_text(encoding="utf-8", errors="replace"), encoding="utf-8", newline="\n")


def apply_optional_patch(kernel_repo: Path, patch_file: Path) -> None:
    if not patch_file.exists():
        return

    # Prefer git-apply because the cloned kernel repo is a git checkout.
    # Use an absolute patch path so the CWD doesn't matter.
    patch_file = patch_file.resolve()
    try:
        subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(patch_file)],
            cwd=str(kernel_repo),
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            "Failed to apply build-fixes patch.\n"
            f"patch: {patch_file}\n"
            f"stdout:\n{e.stdout}\n"
            f"stderr:\n{e.stderr}\n"
        )


def patch_kernel_tree(kernel_repo: Path) -> None:
    drivers_makefile = kernel_repo / "drivers" / "Makefile"
    drivers_kconfig = kernel_repo / "drivers" / "Kconfig"
    defconfig = kernel_repo / "arch" / "arm64" / "configs" / "RMX3265_defconfig"
    dtc_makefile = kernel_repo / "scripts" / "dtc" / "Makefile"

    if not drivers_makefile.exists():
        raise SystemExit(f"Missing {drivers_makefile}")
    if not drivers_kconfig.exists():
        raise SystemExit(f"Missing {drivers_kconfig}")
    if not defconfig.exists():
        raise SystemExit(f"Missing {defconfig}")

    # Fix dtc YAML linking on some vendor 4.14 trees:
    # scripts/Makefile.host uses HOSTLOADLIBES_<prog>, not HOSTLDLIBS_<prog>.
    if dtc_makefile.exists():
        dtc_text = dtc_makefile.read_text(encoding="utf-8", errors="replace")
        if "HOSTLDLIBS_dtc" in dtc_text and "HOSTLOADLIBES_dtc" not in dtc_text:
            dtc_text = dtc_text.replace("HOSTLDLIBS_dtc", "HOSTLOADLIBES_dtc")
            dtc_makefile.write_text(dtc_text, encoding="utf-8", newline="\n")

    # Keep this line simple (spaces only). Using literal "\\t" sequences can break Makefile parsing.
    ensure_line_in_file(drivers_makefile, "obj-$(CONFIG_KSU) += kernelsu/", after_regex=r"^obj-\$\(CONFIG_.*\)\s*\+=.*$")
    ensure_line_in_file(drivers_kconfig, 'source "drivers/kernelsu/Kconfig"')

    # Required configs
    set_defconfig_symbol(defconfig, "KSU", "y")
    set_defconfig_symbol(defconfig, "KPROBES", "y")
    set_defconfig_symbol(defconfig, "KPROBE_EVENTS", "y")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernel", required=True, help="Path to kernel repo")
    ap.add_argument("--kernelsu", required=True, help="Path to KernelSU repo (v0.9.5)")
    args = ap.parse_args()

    kernel_repo = Path(args.kernel).resolve()
    ksu_repo = Path(args.kernelsu).resolve()

    # Apply additional build fixes (kept separate from KernelSU itself).
    # This file lives next to this script in the builder repo.
    builder_root = Path(__file__).resolve().parent
    apply_optional_patch(kernel_repo, builder_root / "patches" / "rmx3265_build_fixes.patch")

    copy_kernelsu_sources(ksu_repo, kernel_repo)
    patch_kernel_tree(kernel_repo)

    print("Applied KernelSU (v0.9.5) non-GKI integration + RMX3265 build fixes.")


if __name__ == "__main__":
    main()
