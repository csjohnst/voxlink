"""Speaker audio playback via PulseAudio Simple API."""

from __future__ import annotations

import logging
import math
import queue
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

# Sentinel to signal the playback thread to stop
_STOP = object()


class PlaybackManager(QObject):
    """Plays audio through speakers in a dedicated thread.

    Uses a plain threading.Thread with a blocking pasimple write loop.
    All PulseAudio operations happen on that thread only.

    Signals:
        level_changed: Emitted with current output RMS level (0.0 - 1.0).
    """

    level_changed = Signal(float)

    def __init__(self, config: AudioConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._queue: queue.Queue = queue.Queue(maxsize=100)
        self._thread: threading.Thread | None = None

    def play(self, pcm_data: bytes) -> None:
        """Queue PCM audio data for playback."""
        if self._thread is None or not self._thread.is_alive():
            return
        try:
            self._queue.put_nowait(pcm_data)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(pcm_data)
            except queue.Full:
                pass

    def start(self) -> None:
        """Start the playback thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        # Clear any stale data
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        self._thread = threading.Thread(
            target=self._playback_loop,
            name="voxlink-playback",
            daemon=True,
        )
        self._thread.start()
        logger.info("Playback started")

    def stop(self) -> None:
        """Stop playback (non-blocking)."""
        # Push sentinel to unblock queue.get()
        try:
            self._queue.put_nowait(_STOP)
        except queue.Full:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            try:
                self._queue.put_nowait(_STOP)
            except queue.Full:
                pass
        logger.info("Playback stop requested")

    def _playback_loop(self) -> None:
        """Blocking playback loop running on a dedicated thread."""
        from pasimple import PaSimple, PA_STREAM_PLAYBACK, PA_SAMPLE_S16LE, PaSimpleError

        device = self._config.output_device or None
        stream = None

        try:
            stream = PaSimple(
                direction=PA_STREAM_PLAYBACK,
                format=PA_SAMPLE_S16LE,
                channels=CHANNELS,
                rate=RATE,
                app_name="voxlink",
                stream_name="playback",
                device_name=device,
                tlength=FRAME_BYTES * 4,
                prebuf=FRAME_BYTES,
                minreq=FRAME_BYTES,
            )
            logger.info("Playback stream opened on device=%s", device or "(default)")
        except Exception:
            logger.exception("Failed to open playback stream on device=%s", device or "(default)")
            return

        try:
            while True:
                try:
                    item = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if item is _STOP:
                    break

                try:
                    stream.write(item)
                except PaSimpleError:
                    logger.exception("Playback write error")
                    break

                level = _compute_rms(item)
                self.level_changed.emit(level)
        except Exception:
            logger.exception("Playback worker crashed")
        finally:
            try:
                stream.drain()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
            logger.info("Playback stream closed")

    def set_device(self, device_name: str) -> None:
        """Switch to a different output device."""
        self._config.output_device = device_name
        if self._thread is not None and self._thread.is_alive():
            self.stop()
            self._thread.join(timeout=2.0)
            self.start()


def _compute_rms(data: bytes) -> float:
    """Compute RMS level normalized to 0.0-1.0 range."""
    n_samples = len(data) // 2
    if n_samples == 0:
        return 0.0
    samples = struct.unpack(f"<{n_samples}h", data)
    sum_sq = sum(s * s for s in samples)
    rms = math.sqrt(sum_sq / n_samples)
    return min(rms / 32767.0, 1.0)
