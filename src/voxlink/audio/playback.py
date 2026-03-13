"""Speaker audio playback via PulseAudio Simple API."""

from __future__ import annotations

import logging
import math
import queue
import struct
import threading

from pasimple import PaSimple, PA_STREAM_PLAYBACK, PA_SAMPLE_S16LE, PaSimpleError
from PySide6.QtCore import QObject, QThread, Signal

from voxlink.config import AudioConfig

logger = logging.getLogger(__name__)

# Mumble standard audio format constants
RATE = 48000
CHANNELS = 1
FRAME_SAMPLES = 960  # 20ms at 48kHz
FRAME_BYTES = FRAME_SAMPLES * CHANNELS * 2  # 16-bit = 2 bytes per sample

# Sentinel to signal the playback thread to stop
_STOP = object()


class _PlaybackWorker(QObject):
    """Worker that runs the blocking playback loop in a QThread."""

    level_changed = Signal(float)

    def __init__(self, device_name: str | None) -> None:
        super().__init__()
        self._device_name = device_name or None
        self._running = False
        self._stream: PaSimple | None = None
        self._queue: queue.Queue = queue.Queue(maxsize=100)
        self._lock = threading.Lock()

    def set_device(self, device_name: str | None) -> None:
        """Set the device name. Must be called before run() or between stop/start."""
        self._device_name = device_name or None

    def enqueue(self, pcm_data: bytes) -> None:
        """Add PCM data to the playback queue (non-blocking, drops on overflow)."""
        try:
            self._queue.put_nowait(pcm_data)
        except queue.Full:
            # Drop oldest frame and add new one to avoid unbounded latency
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(pcm_data)
            except queue.Full:
                pass

    def run(self) -> None:
        """Main playback loop (called when thread starts)."""
        self._running = True
        try:
            self._open_stream()
            while self._running:
                try:
                    item = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if item is _STOP:
                    break

                try:
                    with self._lock:
                        if self._stream is not None:
                            self._stream.write(item)
                except PaSimpleError:
                    if self._running:
                        logger.exception("Playback write error")
                    break

                # Calculate output level
                level = self._compute_rms(item)
                self.level_changed.emit(level)

        except Exception:
            logger.exception("Playback worker crashed")
        finally:
            self._close_stream()

    def stop(self) -> None:
        """Signal the playback loop to stop."""
        self._running = False
        # Push sentinel to unblock the queue.get()
        try:
            self._queue.put_nowait(_STOP)
        except queue.Full:
            pass

    def _open_stream(self) -> None:
        """Open a PulseAudio playback stream."""
        with self._lock:
            self._stream = PaSimple(
                direction=PA_STREAM_PLAYBACK,
                format=PA_SAMPLE_S16LE,
                channels=CHANNELS,
                rate=RATE,
                app_name="voxlink",
                stream_name="playback",
                device_name=self._device_name,
                tlength=FRAME_BYTES * 4,  # ~80ms buffer
                prebuf=FRAME_BYTES,  # start playback after one frame
                minreq=FRAME_BYTES,
            )
        logger.info(
            "Playback stream opened on device=%s",
            self._device_name or "(default)",
        )

    def _close_stream(self) -> None:
        """Close the playback stream if open."""
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.drain()
                except Exception:
                    pass
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
        return min(rms / 32767.0, 1.0)


class PlaybackManager(QObject):
    """Plays audio through speakers in a dedicated thread.

    Signals:
        level_changed: Emitted with current output RMS level (0.0 - 1.0).
    """

    level_changed = Signal(float)

    def __init__(self, config: AudioConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._thread: QThread | None = None
        self._worker: _PlaybackWorker | None = None
        self._running = False

    def play(self, pcm_data: bytes) -> None:
        """Queue PCM audio data for playback."""
        if self._worker is not None:
            self._worker.enqueue(pcm_data)

    def set_device(self, device_name: str) -> None:
        """Switch to a different output device."""
        self._config.output_device = device_name
        if self._running:
            # Restart playback with new device
            self.stop()
            self.start()

    def start(self) -> None:
        """Initialize the playback stream."""
        if self._running:
            logger.warning("Playback already running")
            return

        device = self._config.output_device if self._config.output_device else None

        self._thread = QThread()
        self._thread.setObjectName("playback-thread")
        self._worker = _PlaybackWorker(device)
        self._worker.moveToThread(self._thread)

        # Wire signals
        self._worker.level_changed.connect(self.level_changed)
        self._thread.started.connect(self._worker.run)

        self._running = True
        self._thread.start()
        logger.info("Playback started")

    def stop(self) -> None:
        """Close the playback stream."""
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
        logger.info("Playback stopped")
