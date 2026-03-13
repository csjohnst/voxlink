"""Microphone audio capture via PulseAudio Simple API."""

from __future__ import annotations

import logging
import math
import struct
import threading

from PySide6.QtCore import QObject, Signal

from voxlink.config import AudioConfig

logger = logging.getLogger(__name__)

# Mumble standard audio format constants
RATE = 48000
CHANNELS = 1
FRAME_SAMPLES = 960  # 20ms at 48kHz
FRAME_BYTES = FRAME_SAMPLES * CHANNELS * 2  # 16-bit = 2 bytes per sample


class CaptureManager(QObject):
    """Captures audio from a microphone in a dedicated thread.

    Uses a plain threading.Thread with a blocking pasimple read loop.
    All PulseAudio operations happen on that thread only. Stop is
    non-blocking to avoid freezing the UI.

    Signals:
        audio_captured: Emitted with raw PCM bytes (48kHz, 16-bit, mono).
        level_changed: Emitted with current RMS audio level (0.0 - 1.0).
    """

    audio_captured = Signal(bytes)
    level_changed = Signal(float)

    def __init__(self, config: AudioConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start capturing audio from the configured input device."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._capture_loop,
                name="voxlink-capture",
                daemon=True,
            )
            self._thread.start()
            logger.info("Capture started")

    def stop(self) -> None:
        """Stop audio capture (non-blocking)."""
        self._stop_event.set()
        # Don't join — the thread will exit on its own within ~20ms
        # (one frame read timeout). This avoids blocking the UI thread.
        logger.info("Capture stop requested")

    def _capture_loop(self) -> None:
        """Blocking capture loop running on a dedicated thread."""
        from pasimple import PaSimple, PA_STREAM_RECORD, PA_SAMPLE_S16LE, PaSimpleError

        device = self._config.input_device or None
        stream = None

        try:
            stream = PaSimple(
                direction=PA_STREAM_RECORD,
                format=PA_SAMPLE_S16LE,
                channels=CHANNELS,
                rate=RATE,
                app_name="voxlink",
                stream_name="capture",
                device_name=device,
                fragsize=FRAME_BYTES,
            )
            logger.info("Capture stream opened on device=%s", device or "(default)")
        except Exception:
            logger.exception("Failed to open capture stream on device=%s", device or "(default)")
            return

        try:
            while not self._stop_event.is_set():
                try:
                    data = stream.read(FRAME_BYTES)
                except PaSimpleError:
                    if not self._stop_event.is_set():
                        logger.exception("Capture read error")
                    break
                except Exception:
                    if not self._stop_event.is_set():
                        logger.exception("Capture read unexpected error")
                    break

                if self._stop_event.is_set():
                    break

                self.audio_captured.emit(data)
                level = _compute_rms(data)
                self.level_changed.emit(level)
        finally:
            try:
                stream.close()
            except Exception:
                pass
            logger.info("Capture stream closed")

    def set_device(self, device_name: str) -> None:
        """Switch to a different input device."""
        self._config.input_device = device_name
        if self._thread is not None and self._thread.is_alive():
            self.stop()
            # Wait briefly for the old thread to finish
            self._thread.join(timeout=1.0)
            self.start()

    @property
    def is_capturing(self) -> bool:
        """Whether capture is currently active."""
        return self._thread is not None and self._thread.is_alive()


def _compute_rms(data: bytes) -> float:
    """Compute RMS level normalized to 0.0-1.0 range."""
    n_samples = len(data) // 2
    if n_samples == 0:
        return 0.0
    samples = struct.unpack(f"<{n_samples}h", data)
    sum_sq = sum(s * s for s in samples)
    rms = math.sqrt(sum_sq / n_samples)
    return min(rms / 32767.0, 1.0)
