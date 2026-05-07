"""Progress lines for large uploads (R2 / boto3 and upload-post multipart body)."""

from __future__ import annotations

import os
from typing import Any, BinaryIO


def progress_enabled() -> bool:
    """Set UPLOAD_PROGRESS=0 (or false/off/no) to disable progress lines."""
    v = (os.environ.get("UPLOAD_PROGRESS") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _print_progress_line(label: str, transferred: int, total: int) -> None:
    if total <= 0:
        return
    mb_t = total / (1024 * 1024)
    mb_d = min(transferred, total) / (1024 * 1024)
    pct = 100.0 * min(transferred, total) / total
    print(f"  {label}: {mb_d:.1f} / {mb_t:.1f} MiB ({pct:.1f}%)", flush=True)


def _progress_step_bytes(total: int) -> int:
    """~40 progress ticks, at least 5 MiB per tick, capped at total."""
    if total <= 0:
        return 0
    step = max(total // 40, 5 * 1024 * 1024)
    return min(step, total)


def make_boto3_upload_callback(total_bytes: int, label: str):
    """
    Callback for boto3 ``upload_file``; argument is cumulative bytes transferred.
    Returns None when progress is disabled (omit Callback= in upload_file).
    """
    if not progress_enabled() or total_bytes <= 0:
        return None
    step = _progress_step_bytes(total_bytes)
    last_printed = 0

    def callback(n: int) -> None:
        nonlocal last_printed
        t = min(n, total_bytes)
        if t >= total_bytes:
            if last_printed < total_bytes:
                _print_progress_line(label, total_bytes, total_bytes)
                last_printed = total_bytes
            return
        if t - last_printed < step:
            return
        _print_progress_line(label, t, total_bytes)
        last_printed = t

    return callback


class ProgressBinaryReader:
    """
    Wrap a binary file so ``read()`` reports progress for multipart POST encoding.

    Closes the underlying file when ``close()`` is called.
    """

    __slots__ = ("_raw", "_total", "_read", "_label", "_step", "_next_threshold")

    def __init__(self, raw: BinaryIO, total: int, label: str):
        self._raw = raw
        self._total = total
        self._read = 0
        self._label = label
        if not progress_enabled() or total <= 0:
            self._step = 0
            self._next_threshold = 0
        else:
            self._step = _progress_step_bytes(total)
            self._next_threshold = self._step

    def read(self, size: int = -1) -> bytes:
        data = self._raw.read(size)
        self._report(len(data))
        return data

    def readinto(self, b: Any) -> int:
        n = self._raw.readinto(b)
        if n is not None and n > 0:
            self._report(n)
        return n

    def _report(self, delta: int) -> None:
        self._read += delta
        if self._step <= 0:
            return
        while self._next_threshold and self._read >= self._next_threshold:
            _print_progress_line(self._label, min(self._read, self._total), self._total)
            if self._read >= self._total:
                self._next_threshold = 0
                break
            nxt = self._next_threshold + self._step
            self._next_threshold = nxt if nxt <= self._total else self._total

    def close(self) -> None:
        self._raw.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False

    def __getattr__(self, name: str):
        return getattr(self._raw, name)
