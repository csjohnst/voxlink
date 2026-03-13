"""Tests for audio device enumeration."""

from voxlink.audio.devices import AudioDevice


def test_audio_device_dataclass():
    """AudioDevice holds device info."""
    dev = AudioDevice(name="alsa_input.usb-mic", description="USB Microphone")
    assert dev.name == "alsa_input.usb-mic"
    assert dev.description == "USB Microphone"
    assert dev.is_monitor is False
