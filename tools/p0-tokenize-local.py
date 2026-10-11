"""Standalone offline tokenizer helper; no SDK, secrets, SQLite, grants or downloads."""
from __future__ import annotations

import ctypes
import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from typing import Any

MODEL = "gpt-5.6-terra"
ENCODING_URL = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
ENCODING_SHA = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
MODULE_ROOTS = {"tiktoken", "tiktoken_ext", "regex", "requests", "urllib3", "certifi", "charset_normalizer", "idna"}
MANIFEST_FIELDS = {"schema", "python_path", "python_sha256", "package_root", "package_version", "files",
    "model_mapping_sha256", "encoding_path", "encoding_sha256", "cache_root"}


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode(raw: bytes) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        if len(dict(pairs)) != len(pairs):
            raise ValueError("DUPLICATE")
        return dict(pairs)
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE")))
    if not isinstance(value, dict) or canonical(value) != raw:
        raise ValueError("NONCANONICAL")
    return value


class RetainedPaths:
    """Pin files against WRITE/DELETE and every parent against DELETE."""
    def __init__(self) -> None:
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.create = self.kernel.CreateFileW
        self.create.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
        self.create.restype = ctypes.c_void_p
        self.identify = self.kernel.GetFileInformationByHandleEx
        self.identify.argtypes, self.identify.restype = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32), ctypes.c_int
        self.close_handle = self.kernel.CloseHandle
        self.close_handle.argtypes, self.close_handle.restype = (ctypes.c_void_p,), ctypes.c_int
        self.held: dict[Path, int] = {}

    def retain(self, value: str, *, file: bool) -> Path:
        path = Path(value)
        if not path.is_absolute() or len(path.drive) != 2 or ".." in path.parts:
            raise ValueError("LOCAL_ABSOLUTE_REQUIRED")
        paths = (*reversed(path.parents), path)
        class FileIdentity(ctypes.Structure):
            _fields_ = [("volume", ctypes.c_uint64), ("file_id", ctypes.c_ubyte * 16)]
        for item in paths:
            if item in self.held:
                continue
            before = item.lstat()
            is_file = file and item == path
            if (getattr(before, "st_file_attributes", 0) & 0x400
                    or (is_file and not item.is_file()) or (not is_file and not item.is_dir())):
                raise ValueError("REPARSE_OR_TYPE_REJECTED")
            handle = self.create(str(item), 0x80000000, 1 if is_file else 3, None, 3,
                0x00200000 if is_file else 0x02200000, None)
            if handle in (None, ctypes.c_void_p(-1).value):
                raise ValueError("HANDLE_REFUSED")
            self.held[item] = handle
            opened = FileIdentity()
            after = item.lstat()
            if (not self.identify(handle, 18, ctypes.byref(opened), ctypes.sizeof(opened))
                    or (opened.volume, int.from_bytes(bytes(opened.file_id), "little")) != (before.st_dev, before.st_ino)
                    or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)):
                raise ValueError("IDENTITY_CHANGED")
        return path

    def close(self) -> None:
        for handle in reversed(self.held.values()):
            self.close_handle(handle)
        self.held.clear()


def token_counts(value: object, encode: Any) -> int:
    if isinstance(value, str):
        return len(encode(value, disallowed_special=()))
    if isinstance(value, dict):
        return sum(token_counts(k, encode) + token_counts(v, encode) for k,v in value.items())
    if isinstance(value, list):
        return sum(token_counts(item, encode) for item in value)
    return 0


def disable_unverified_bytecode_cache() -> None:
    # -B forbids writes but still reads timestamp-valid .pyc files. Route all
    # reads to a fresh unpredictable absent prefix before third-party imports,
    # so only the verified retained sources/binaries can execute. No directory
    # or cache is created, and historical bytecode remains unchanged.
    prefix = Path(sys.executable).parent / ("p0-no-bytecode-" + os.urandom(32).hex())
    if os.path.lexists(prefix):
        raise ValueError("BYTECODE_CACHE_PREFIX_COLLISION")
    sys.pycache_prefix = str(prefix)
    sys.dont_write_bytecode = True


def execute(envelope: dict[str, Any], retained: RetainedPaths) -> dict[str, object]:
    if set(envelope) != {"manifest", "manifest_sha256", "request_body_utf8"}:
        raise ValueError("ENVELOPE_FIELDS")
    manifest = envelope["manifest"]
    if (not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS
            or manifest["schema"] != "P0-LOCAL-TOKENIZER-MANIFEST-1.0"
            or digest(canonical(manifest)) != envelope["manifest_sha256"]):
        raise ValueError("MANIFEST_CHANGED")
    executable = retained.retain(manifest["python_path"], file=True)
    if executable != Path(sys.executable) or digest(executable.read_bytes()) != manifest["python_sha256"]:
        raise ValueError("INTERPRETER_CHANGED")
    package_root = retained.retain(manifest["package_root"], file=False)
    if package_root != executable.parent.parent / "Lib" / "site-packages":
        raise ValueError("PACKAGE_ROOT_CHANGED")
    expected = manifest["files"]
    if not isinstance(expected, dict) or not expected:
        raise ValueError("PACKAGE_FILES_REQUIRED")
    actual = {path.relative_to(package_root).as_posix(): path for module in MODULE_ROOTS
        for path in (package_root / module).rglob("*") if path.is_file() and "__pycache__" not in path.parts}
    if set(actual) != set(expected):
        raise ValueError("PACKAGE_COVERAGE_CHANGED")
    for name,path in actual.items():
        retained.retain(str(path), file=True)
        if digest(path.read_bytes()) != expected[name]:
            raise ValueError("PACKAGE_CHANGED")
    model_path = package_root / "tiktoken" / "model.py"
    if digest(model_path.read_bytes()) != manifest["model_mapping_sha256"]:
        raise ValueError("MODEL_MAPPING_CHANGED")
    cache = retained.retain(manifest["cache_root"], file=False)
    encoding_path = retained.retain(manifest["encoding_path"], file=True)
    expected_path = cache / hashlib.sha1(ENCODING_URL.encode()).hexdigest()
    if (encoding_path != expected_path or manifest["encoding_sha256"] != ENCODING_SHA
            or digest(encoding_path.read_bytes()) != ENCODING_SHA):
        raise ValueError("ENCODING_CACHE_CHANGED")
    # -I -S avoids sitecustomize, .pth files and ambient PYTHONPATH before proof.
    disable_unverified_bytecode_cache()
    sys.path.insert(0, str(package_root))
    os.environ["TIKTOKEN_CACHE_DIR"] = str(cache)
    tiktoken = importlib.import_module("tiktoken")
    model = importlib.import_module("tiktoken.model")
    namespace = importlib.import_module("tiktoken_ext")
    if (Path(str(tiktoken.__file__)) != package_root / "tiktoken" / "__init__.py"
            or Path(str(model.__file__)) != model_path
            or set(Path(item) for item in namespace.__path__) != {package_root / "tiktoken_ext"}
            or importlib.metadata.version("tiktoken") != manifest["package_version"]
            or model.encoding_name_for_model(MODEL) != "o200k_base"):
        raise ValueError("OFFICIAL_MODEL_RESOLVER_REFUSED")
    encoding = tiktoken.get_encoding("o200k_base")
    body = envelope["request_body_utf8"]
    if not isinstance(body, str) or not 0 < len(body.encode()) < 250000:
        raise ValueError("REQUEST_SIZE")
    request = decode(body.encode())
    return {"schema": "P0-NORMAL-TOKENIZER-PROOF-1.0", "model": MODEL,
        "recognition": "OFFICIAL_UNMODIFIED_PACKAGE_RESOLVER", "encoding": "o200k_base",
        "manifest_sha256": envelope["manifest_sha256"], "request_sha256": digest(body.encode()),
        "model_mapping_sha256": manifest["model_mapping_sha256"], "encoding_sha256": ENCODING_SHA,
        "all_string_values_and_keys_tokens": token_counts(request, encoding.encode),
        "serialized_json_tokens": len(encoding.encode(body, disallowed_special=())),
        "network_forbidden_during_count": True, "provider_calls": 0}


def main() -> int:
    if sys.platform != "win32" or sys.version_info[:2] != (3,12):
        return 2
    held = RetainedPaths()
    try:
        raw = sys.stdin.buffer.read(8_000_001)
        if len(raw) > 8_000_000:
            return 2
        result = execute(decode(raw), held)
        sys.stdout.buffer.write(canonical(result))
        return 0
    except Exception:
        sys.stderr.write("P0_LOCAL_TOKENIZER_REFUSED\n")
        return 2
    finally:
        held.close()


if __name__ == "__main__":
    raise SystemExit(main())
