#!/usr/bin/env python3
"""把 OpenWrt 的 .ipk（opkg 格式）转换为 .apk（APKv2 格式）。

纯 Python 3 实现，只依赖标准库，无需安装任何第三方包。
产出的是 APKv2，而 apk-tools 3（OpenWrt 25.12 起默认）向下兼容，可直接安装：

    apk add --allow-untrusted ./package.apk

用法:
    ./ipk2apk.py package.ipk [-o output.apk]

基于 https://github.com/rychly/openwrt-ipk2apk (MIT License) 修改，
针对 OpenWrt 25.12 的兼容性问题做了以下修正：
  1. arch 字段：把 ipk 的 "all" 翻译成 APK 要求的 "noarch"
     （apk-tools 3.0 起会校验包架构，只认 noarch 为通用值，写 all 会被拒绝安装）
  2. pkgver 字段：补全 APK 要求的 -rN 后缀（如 1.0.0 -> 1.0.0-r1）
  3. 文件权限：不依赖文件系统上的 mode 位（跨平台不可靠），
     改为按路径规则重建：目录 0755，bin/sbin/init.d 下或带 shebang 的文件 0755，其余 0644
  4. 安装脚本（.post-install 等）固定为 0755，否则 apk 拒绝执行

SPDX-License-Identifier: MIT
"""

import os
import sys
import tarfile
import tempfile
import argparse
import re
import hashlib
import gzip
import io
from typing import Dict, List


def parse_control_file(control_path: str) -> Dict[str, str]:
    """Parses the IPK control file into a metadata dictionary."""
    metadata: Dict[str, str] = {}
    with open(control_path, "r", encoding="utf-8") as f:
        key = None
        for line in f:
            # Check for continuation lines BEFORE stripping: in Debian/IPK
            # control format, continuation lines start with whitespace.
            if line.startswith((" ", "\t")) and key:
                # Handle multi-line values (like Description)
                metadata[key] += f" {line.strip()}"
                continue
            line = line.strip()
            if not line:
                key = None
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                metadata[key] = value.strip()
    return metadata


def _apk_dep_constraint(dep: str) -> str:
    """Converts a single IPK dependency token to APK notation.

    IPK/Debian uses parenthesised operators, e.g., 'pkg (>= 1.0)'.
    APK uses inline operators without parentheses, e.g., 'pkg>=1.0'.

    Operator mapping:
      (= ver)  -> =ver   (exact)
      (>= ver) -> >=ver
      (<= ver) -> <=ver
      (>> ver) -> >ver   (Debian strict-greater)
      (<< ver) -> <ver   (Debian strict-less)
      (> ver)  -> >ver   (OpenWrt style)
      (< ver)  -> <ver   (OpenWrt style)
    """
    dep = dep.strip()
    match = re.match(r"^(\S+)\s*\(\s*(=|>=|<=|>>|<<|>|<)\s*([^)]+)\)$", dep)
    if not match:
        return dep
    pkg, op, ver = match.group(1).strip(), match.group(2), match.group(3).strip()
    # Normalise Debian strict operators to their APK equivalents
    apk_op = {">>": ">", "<<": "<"}.get(op, op)
    return f"{pkg}{apk_op}{ver}"


def format_dependencies(depends_str: str) -> List[str]:
    """Converts IPK dependency expressions to APK notation.

    Version constraints are translated to APK's inline format (e.g.,
    'libssl (>= 1.1)' becomes 'libssl>=1.1').  OR-alternatives ('|') are
    preserved.  Each comma-separated entry becomes one list element.
    """
    if not depends_str:
        return []
    result = []
    for dep_expr in depends_str.split(","):
        # Split on '|' for alternatives, convert each token individually
        alternatives = [
            _apk_dep_constraint(a) for a in dep_expr.split("|") if a.strip()
        ]
        if alternatives:
            result.append("|".join(alternatives))
    return result


def format_provides(provides_str: str) -> List[str]:
    """Converts IPK Provides into APK provides format.

    APK supports versioned provides using '=' only (e.g., 'libfoo=1.0').
    Exact-version constraints '(= <ver>)' are converted to that form via
    _apk_dep_constraint(); all other version constraints are stripped because
    APK does not support range operators in 'provides'.
    """
    if not provides_str:
        return []
    result = []
    for item in provides_str.split(","):
        item = item.strip()
        if not item:
            continue
        converted = _apk_dep_constraint(item)
        # APK provides only support exact '=' version constraints; drop ranges
        if re.search(r"[<>]", converted):
            converted = re.sub(r"[<>].*$", "", converted).strip()
        if converted:
            result.append(converted)
    return result


def get_directory_size(path: str) -> int:
    """Calculates the total uncompressed size of all files in a directory."""
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size


def calculate_sha256(filepath: str) -> str:
    """Calculates the SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256.update(byte_block)
    return sha256.hexdigest()


def create_pkginfo_content(
    metadata: Dict[str, str], data_size: int, data_hash: str
) -> str:
    """Generates the required text content for the .PKGINFO file."""
    # apk-tools >= 3.0 validates the arch field against /etc/apk/arch and only
    # ever whitelists "noarch". OpenWrt translates PKGARCH:=all -> noarch for
    # exactly this reason, so do the same here.
    raw_arch = metadata.get("Architecture", "unknown")
    arch = "noarch" if raw_arch in ("all", "noarch") else raw_arch

    # apk expects pkgver in <version>-r<release> form (e.g. 1.0.0-r1).
    raw_ver = metadata.get("Version", "1.0.0")
    pkgver = raw_ver if re.search(r"-r\d+$", raw_ver) else f"{raw_ver}-r1"

    pkginfo = [
        f"pkgname = {metadata.get('Package', 'unknown')}",
        f"pkgver = {pkgver}",
        f"pkgdesc = {metadata.get('Description', 'Converted from IPK')}",
        f"arch = {arch}",
        f"size = {data_size}",
        f"datahash = {data_hash}",
    ]

    if "Maintainer" in metadata:
        pkginfo.append(f"maintainer = {metadata['Maintainer']}")
    if "Homepage" in metadata:
        pkginfo.append(f"url = {metadata['Homepage']}")
    if "License" in metadata:
        pkginfo.append(f"license = {metadata['License']}")
    if "Depends" in metadata:
        # APK requires one "depend = <name>" line per dependency
        for dep in format_dependencies(metadata["Depends"]):
            pkginfo.append(f"depend = {dep}")
    if "Provides" in metadata:
        # APK requires one "provides = <name>[=version]" line per provided package
        for prov in format_provides(metadata["Provides"]):
            pkginfo.append(f"provides = {prov}")
    if "Conflicts" in metadata:
        # APK uses "conflict" (singular) for package conflicts
        for conf in format_dependencies(metadata["Conflicts"]):
            pkginfo.append(f"conflict = {conf}")
    if "Replaces" in metadata:
        # APK requires one "replaces = <name>" line per replaced package
        for repl in format_dependencies(metadata["Replaces"]):
            pkginfo.append(f"replaces = {repl}")

    return "\n".join(pkginfo) + "\n"


EXEC_DIRS = ("bin", "sbin", "init.d", "libexec", "rc.d", "hotplug.d")


def _sane_mode(info: tarfile.TarInfo, arcname: str, full_path: str) -> int:
    """Derives a sane POSIX mode for a member.

    tarfile.extractall() silently drops mode bits on Windows, so every file ends
    up 0666 and the package loses its executables. Rather than trusting the
    filesystem, decide from the path and the shebang line.
    """
    parts = arcname.replace("\\", "/").split("/")
    if info.isdir():
        return 0o755
    if any(p in EXEC_DIRS for p in parts[:-1]):
        return 0o755
    if info.issym():
        return 0o777
    try:
        with open(full_path, "rb") as fh:
            if fh.read(2) == b"#!":
                return 0o755
    except OSError:
        pass
    return 0o644


def inject_files_with_pax_checksums(tar: tarfile.TarFile, src_dir: str) -> None:
    """
    Traverses a directory and adds files to a tar archive.
    Critically, it calculates the SHA1 hash for every regular file and
    injects it into the tar archive via the APK-TOOLS PAX extended header.
    """
    for root, dirs, files in os.walk(src_dir):
        # Ensure deterministic ordering
        dirs.sort()
        files.sort()

        # Add directories
        for d in dirs:
            full_path = os.path.join(root, d)
            arcname = os.path.relpath(full_path, src_dir)
            info = tar.gettarinfo(full_path, arcname)
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mode = _sane_mode(info, arcname, full_path)
            tar.addfile(info)

        # Add files with SHA1 injection
        for f in files:
            full_path = os.path.join(root, f)
            arcname = os.path.relpath(full_path, src_dir)
            info = tar.gettarinfo(full_path, arcname)
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mode = _sane_mode(info, arcname, full_path)

            if info.isfile():
                sha1 = hashlib.sha1()
                with open(full_path, "rb") as f_in:
                    for chunk in iter(lambda: f_in.read(65536), b""):
                        sha1.update(chunk)

                # Core APK requirement: store hash in PAX extended header
                info.pax_headers = {"APK-TOOLS.checksum.SHA1": sha1.hexdigest()}

                with open(full_path, "rb") as f_in:
                    tar.addfile(info, f_in)
            else:
                # Symlinks and special files do not require checksums
                tar.addfile(info)


def convert_package(ipk_file: str, apk_file: str) -> None:
    print(f"[*] Extracting IPK: {ipk_file}")

    # Dynamically handle Python 3.12+ tarfile extraction filters (PEP 706)
    # to avoid DeprecationWarnings while maintaining backward compatibility.
    extract_kwargs = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            with tarfile.open(ipk_file, "r:gz") as ipk:
                ipk.extractall(path=tmpdir, **extract_kwargs)
        except tarfile.ReadError as e:
            raise ValueError("The source file is not a valid tar.gz archive.") from e

        control_tar_path = os.path.join(tmpdir, "control.tar.gz")
        orig_data_tar_path = os.path.join(tmpdir, "data.tar.gz")

        for required_path, name in [
            (control_tar_path, "control.tar.gz"),
            (orig_data_tar_path, "data.tar.gz"),
        ]:
            if not os.path.exists(required_path):
                raise FileNotFoundError(
                    f"Expected member '{name}' not found in the IPK archive."
                )

        # ==========================================
        # STEP 1: Process IPK Metadata
        # ==========================================
        control_dir = os.path.join(tmpdir, "control_ext")
        os.makedirs(control_dir, exist_ok=True)
        with tarfile.open(control_tar_path, "r:gz") as c_tar:
            c_tar.extractall(path=control_dir, **extract_kwargs)

        control_file = os.path.join(control_dir, "control")
        if not os.path.exists(control_file):
            raise FileNotFoundError(
                "Expected 'control' file not found in control.tar.gz."
            )
        control_meta = parse_control_file(control_file)

        # ==========================================
        # STEP 2: Process Data Stream
        # ==========================================
        data_dir = os.path.join(tmpdir, "data_ext")
        os.makedirs(data_dir, exist_ok=True)
        with tarfile.open(orig_data_tar_path, "r:gz") as d_tar:
            d_tar.extractall(path=data_dir, **extract_kwargs)

        data_size = get_directory_size(data_dir)
        new_data_gz_path = os.path.join(tmpdir, "new_data.tar.gz")

        print("[*] Generating data stream (with SHA1 PAX headers)...")
        # Data segment MUST be PAX_FORMAT for extended headers to work
        with gzip.GzipFile(new_data_gz_path, "wb", mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as d_tar:
                inject_files_with_pax_checksums(d_tar, data_dir)

        data_hash = calculate_sha256(new_data_gz_path)

        # ==========================================
        # STEP 3: Process Control Stream
        # ==========================================
        pkginfo_content = create_pkginfo_content(control_meta, data_size, data_hash)
        control_tar_buffer = io.BytesIO()

        # Control segment MUST be GNU_FORMAT (no PAX headers allowed here).
        # This ensures .PKGINFO is physically the first file without any hidden pax blocks.
        with tarfile.open(
            fileobj=control_tar_buffer, mode="w", format=tarfile.GNU_FORMAT
        ) as c_tar:

            # Add .PKGINFO first
            info = tarfile.TarInfo(".PKGINFO")
            pkginfo_bytes = pkginfo_content.encode("utf-8")
            info.size = len(pkginfo_bytes)
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mode = 0o644
            c_tar.addfile(info, io.BytesIO(pkginfo_bytes))

            # Map install scripts from IPK format to APK format
            script_map = {
                "preinst": ".pre-install",
                "postinst": ".post-install",
                "prerm": ".pre-deinstall",
                "postrm": ".post-deinstall",
            }

            for item in sorted(os.listdir(control_dir)):
                if item in script_map:
                    item_path = os.path.join(control_dir, item)
                    arcname = script_map[item]
                    info = c_tar.gettarinfo(item_path, arcname)
                    info.uid = info.gid = 0
                    info.uname = info.gname = "root"
                    # Must be executable or apk will refuse to run the script
                    info.mode = 0o755

                    with open(item_path, "rb") as f_in:
                        c_tar.addfile(info, f_in)

            # MAGIC: Capture the exact stream length before EOF null blocks are added by tarfile
            valid_tar_length = c_tar.offset

        # Truncate the EOF null blocks to allow proper stream chaining
        tar_data_truncated = control_tar_buffer.getvalue()[:valid_tar_length]

        new_control_gz_path = os.path.join(tmpdir, "new_control.tar.gz")
        print(
            "[*] Generating control stream (strict GNU_FORMAT, stripping EOF blocks)..."
        )
        with gzip.GzipFile(new_control_gz_path, "wb", mtime=0) as gz:
            gz.write(tar_data_truncated)

        # ==========================================
        # STEP 4: Final Assembly (Concatenation)
        # ==========================================
        print(f"[*] Concatenating streams into: {apk_file}")
        with open(apk_file, "wb") as apk:
            with open(new_control_gz_path, "rb") as c:
                apk.write(c.read())
            with open(new_data_gz_path, "rb") as d:
                apk.write(d.read())

    print("[+] Conversion completed successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Converts an OpenWrt .ipk package into a strict Alpine/OpenWrt .apk v2 package."
    )
    parser.add_argument("ipk_file", help="Path to the source .ipk file")
    parser.add_argument(
        "-o", "--output", help="Optional output path for the .apk file", default=None
    )
    args = parser.parse_args()

    source_path = args.ipk_file
    if not os.path.exists(source_path):
        print(f"[!] Error: Source file '{source_path}' does not exist.")
        sys.exit(1)

    target_path = args.output if args.output else source_path.rsplit(".", 1)[0] + ".apk"
    try:
        convert_package(source_path, target_path)
    except (ValueError, FileNotFoundError) as e:
        print(f"[!] Error: {e}")
        sys.exit(1)
