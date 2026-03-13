"""Microphone audio capture via PulseAudio Simple API."""

from __future__ import annotations

import logging
import math
import struct
import threading

from pasimple import PaSimple, PA_STREAM_RECORD, PA_SAMPLE_S16LE, PaSimpleError
from PySide6.QtCore import QObject, QThread, Signal

from voxlink.config import AudioConfig

logger = logging.getLogger(__name__)

# Mumble standard audio format constants
RATE = 48000
CHANNELS = 1
FRAME_SAMPLES = 960  # 20ms at 48kHz
FRAME_BYTES = FRAME_SAMPLES * CHANNELS * 2  # 16-bit = 2 bytes per sample


class _CaptureWorker(QObject):
    """Worker that runs the blocking capture loop in a QThread."""

    audio_captured = Signal(bytes)
    level_changed = Signal(float)

    def __init__(self, device_name: str | None) -> None:
        super().__init__()
        self._device_name = device_name or None
        self._running = False
        self._stream: PaSimple | None = None
        self._lock = threading.Lock()

    def set_device(self, device_name: str | None) -> None:
        """Set the device name. Must be called before run() or between stop/start."""
        self._device_name = device_name or None

    def run(self) -> None:
        """Main capture loop (called when thread starts)."""
        self._running = True
        try:
            self._open_stream()
            while self._running:
                try:
                    data = self._stream.read(FRAME_BYTES)  # type: ignore[union-attr]
                except PaSimpleError:
                    if self._running:
                        logger.exception("Capture read error")
                    break

                if not self._running:
                    break

                self.audio_captured.emit(data)

                # Calculate RMS level
                level = self._compute_rms(data)
                self.level_changed.emit(level)

        except Exception:
            logger.exception("Capture worker crashed")
        finally:
            self._close_stream()

    def stop(self) -> None:
        """Signal the capture loop to stop."""
        self._running = False
        # Close the stream to unblock the read() call
        self._close_stream()

    def _open_stream(self) -> None:
        """Open a PulseAudio capture stream."""
        with self._lock:
            self._stream = PaSimple(
                direction=PA_STREAM_RECORD,
                format=PA_SAMPLE_S16LE,
                channels=CHANNELS,
                rate=RATE,
                app_name="voxlink",
                stream_name="capture",
                device_name=self._device_name,
                fragsize=FRAME_BYTES,
            )
        logger.info(
            "Capture stream opened on device=%s",
            self._device_name or "(default)",
        )

    def _close_stream(self) -> None:
        """Close the capture stream if open."""
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

    @staticmethod
    def _compute_rms(data: bytes) -> float:
        """Compute RMS level normalized to 0.0-1.0 range."""
        n_samples = len(data) // 2
        if n_samples == 0:
            return 0.0
        samples = struct.unpack(f"<{n_samples}h", data)
        sum_sq = sum(s * s for s in samples)
        rms = math.sqrt(sum_sq / n_samples)
        # Normalize: max S16 value is 32767
        return min(rms / 32767.0, 1.0)


class CaptureManager(QObject):
    """Captures audio from a microphone in a dedicated thread.

    Signals:
        audio_captured: Emitted with raw PCM bytes (48kHz, 16-bit, mono).
        level_changed: Emitted with current RMS audio level (0.0 - 1.0).
    """

    audio_captured = Signal(bytes)
    level_changed = Signal(float)

    def __init__(self, config: AudioConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._running = False
        self._thread: QThread | None = None
        self._worker: _CaptureWorker | None = None

    def start(self) -> None:
        """Start capturing audio from the configured input device."""
        if self._running:
            logger.warning("Capture already running")
            return

        device = self._config.input_device if self._config.input_device else None

        self._thread = QThread()
        self._thread.setObjectName("capture-thread")
        self._worker = _CaptureWorker(device)
        self._worker.moveToThread(self._thread)

        # Wire signals
        self._worker.audio_captured.connect(self.audio_captured)
        self._worker.level_changed.connect(self.level_changed)
        self._thread.started.connect(self._worker.run)

        self._running = True
        self._thread.start()
        logger.info("Capture started")

    def stop(self) -> None:
        """Stop audio capture."""
        if not self._running:
            return

        self._running = False

        if self._worker is not None:
            self._worker.stop()

        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
            self._thread = None

        self._worker = None
        logger.info("Capture stopped")

    def set_device(self, device_name: str) -> None:
        """Switch to a different input device."""
        self._config.input_device = device_name
        if self._running:
            # Restart capture with new device
            self.stop()
            self.start()

    @property
    def is_capturing(self) -> bool:
        """Whether capture is currently active."""
        return self._running
