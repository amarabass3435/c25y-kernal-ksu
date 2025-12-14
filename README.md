# RMX3265 (Realme C25Y) KernelSU kernel builder

Builds a KernelSU-enabled kernel for **RMX3265 / Realme C25Y (Android 11 / vendor 4.14 tree)** using GitHub Actions or locally.
This repository does **not** include the full Realme kernel source and does **not** publish any proprietary boot images.

## What it does

1. Clones the upstream Realme kernel source
2. Clones **KernelSU v0.9.5** (last release with non‑GKI support)
3. Applies:
	 - KernelSU integration (adds `drivers/kernelsu`, wires `Kconfig/Makefile`, enables `CONFIG_KSU` + `CONFIG_KPROBES`)
	 - Extra build fixes in `patches/rmx3265_build_fixes.patch` (vendor-tree compile fixes)
4. Builds `Image` / `Image.gz` and uploads them as GitHub Actions artifacts

This workflow does **not** create or publish `boot.img`.
You must repack your own stock boot image locally.

## GitHub Actions (recommended)

1. Open your repository on GitHub.
2. Go to **Actions**.
3. Select **Build RMX3265 kernel + KernelSU (non-GKI)**.
4. Click **Run workflow**.
5. When the run finishes, download artifacts from the run summary:
	- `RMX3265-Image` (just `Image` and `Image.gz`)
	- `RMX3265-KernelSU-build` (full build outputs)
	- `RMX3265-build-log` (build log)

## Local build (Linux)

### Dependencies (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
	bc bison build-essential ca-certificates flex git \
	gcc-aarch64-linux-gnu gcc-arm-linux-gnueabi \
	libelf-dev libssl-dev libyaml-dev python3 rsync dwarves
```

### Build steps

```bash
git clone --depth 1 https://github.com/realme-kernel-opensource/realme_C25Y-AndroidR-kernel-source.git kernel
git clone --depth 1 --branch v0.9.5 https://github.com/tiann/KernelSU.git kernelsu

python3 ./apply_kernelsu.py --kernel ./kernel --kernelsu ./kernelsu

cd kernel
make O=out_ksu RMX3265_defconfig
make -j"$(nproc)" O=out_ksu \
	ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi- \
	KCFLAGS='-Wno-error' Image dtbs
```

Outputs:

- `kernel/out_ksu/arch/arm64/boot/Image`
- `kernel/out_ksu/arch/arm64/boot/Image.gz`

## Repacking boot.img (local only)

High-level steps:

1. Unpack **your own** stock `boot.img`
2. Replace the kernel with the newly built `Image` (or `Image.gz` if your device uses a gzipped kernel)
3. Repack using the **same header/version/pagesize/offsets/cmdline** as stock

This approach avoids sharing proprietary blobs while still letting you build and flash a KernelSU kernel.

## Safety / disclaimer

Flashing a boot image can soft-brick the device. Always keep a known-good stock `boot.img` and have a recovery/unbrick plan.

