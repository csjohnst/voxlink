"""Mumble server client wrapping pymumble 2.0 (sourcehut fork)."""

from __future__ import annotations

import enum
import logging
import struct
import sys
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

import mumble as pymumble
from mumble.audio import AUDIO_CODEC
from mumble.constants import UDP_MSG_TYPE
from mumble.mumble import MumbleUDP

from voxlink.config import ServerConfig
from voxlink.mumble.events import MumbleEvents

logger = logging.getLogger(__name__)


def _decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    """Decode a Mumble-style varint from data starting at offset.

    Returns (value, new_offset).
    """
    if offset >= len(data):
        return 0, offset
    b = data[offset]
    if (b & 0x80) == 0:
        # 7-bit positive number
        return b & 0x7F, offset + 1
    elif (b & 0xC0) == 0x80:
        # 14-bit positive number
        if offset + 1 >= len(data):
            return 0, offset + 2
        return ((b & 0x3F) << 8) | data[offset + 1], offset + 2
    elif (b & 0xE0) == 0xC0:
        # 21-bit positive number
        if offset + 2 >= len(data):
            return 0, offset + 3
        return (
            ((b & 0x1F) << 16) | (data[offset + 1] << 8) | data[offset + 2],
            offset + 3,
        )
    elif (b & 0xF0) == 0xE0:
        # 28-bit positive number
        if offset + 3 >= len(data):
            return 0, offset + 4
        return (
            ((b & 0x0F) << 24)
            | (data[offset + 1] << 16)
            | (data[offset + 2] << 8)
            | data[offset + 3],
            offset + 4,
        )
    elif (b & 0xF4) == 0xF0:
        # 32-bit positive number
        if offset + 4 >= len(data):
            return 0, offset + 5
        val = struct.unpack_from("!I", data, offset + 1)[0]
        return val, offset + 5
    elif (b & 0xFC) == 0xF8:
        # 64-bit number
        if offset + 8 >= len(data):
            return 0, offset + 9
        val = struct.unpack_from("!Q", data, offset + 1)[0]
        return val, offset + 9
    elif (b & 0xFC) == 0xFC:
        # Negative recursive varint
        inner, new_off = _decode_varint(data, offset + 1)
        return -inner, new_off
    else:
        return 0, offset + 1


def _patch_sound_received(mumble_obj) -> None:
    """Monkey-patch mumble_obj.sound_received to handle legacy audio format.

    The pymumble 2.0 sourcehut fork only understands the new protobuf-based
    UDP format (MumbleUDP_pb2.Audio). But many Mumble servers still send audio
    in the legacy format where byte 0 = (type << 5) | target, followed by
    varint-encoded session, sequence, and opus data length + payload.

    This patch detects legacy-format packets and decodes them manually.
    """
    original_sound_received = mumble_obj.sound_received

    def patched_sound_received(plaintext: bytes) -> None:
        if len(plaintext) < 2:
            return

        header = plaintext[0]

        # New protobuf format: header is UDP_MSG_TYPE enum (0=Audio, 1=Ping)
        try:
            UDP_MSG_TYPE(header)
            # Valid new format — use original handler
            original_sound_received(plaintext)
            return
        except ValueError:
            pass

        # Legacy format: header = (type << 5) | target
        audio_type = (header >> 5) & 0x07
        target = header & 0x1F

        if audio_type != 4:  # 4 = OPUS
            logger.debug("Legacy audio type %d not OPUS, ignoring", audio_type)
            return

        offset = 1
        # Session ID (server→client packets include sender session)
        session_id, offset = _decode_varint(plaintext, offset)
        # Sequence number
        sequence, offset = _decode_varint(plaintext, offset)
        # Opus data: varint where bit 13 = terminator, bits 0-12 = length
        opus_header, offset = _decode_varint(plaintext, offset)
        is_terminator = bool(opus_header & 0x2000)
        opus_len = opus_header & 0x1FFF

        if offset + opus_len > len(plaintext):
            logger.warning("Legacy audio packet truncated")
            return

        opus_data = plaintext[offset : offset + opus_len]

        logger.debug(
            "Legacy audio: session=%d, seq=%d, opus_len=%d, terminator=%s",
            session_id, sequence, opus_len, is_terminator,
        )

        # Build a fake protobuf Audio message
        from mumble import MumbleUDP_pb2
        audio_pb = MumbleUDP_pb2.Audio()
        audio_pb.sender_session = session_id
        audio_pb.frame_number = sequence
        audio_pb.opus_data = bytes(opus_data)
        audio_pb.is_terminator = is_terminator
        audio_pb.context = target

        MumbleUDP.receive_audio(mumble_obj, audio_pb)

    mumble_obj.sound_received = patched_sound_received


def _encode_varint(value: int) -> bytes:
    """Encode an integer as a Mumble-style varint."""
    if 0 <= value < 0x80:
        return bytes([value & 0x7F])
    elif 0 <= value < 0x4000:
        return bytes([0x80 | ((value >> 8) & 0x3F), value & 0xFF])
    elif 0 <= value < 0x200000:
        return bytes([
            0xC0 | ((value >> 16) & 0x1F),
            (value >> 8) & 0xFF,
            value & 0xFF,
        ])
    elif 0 <= value < 0x10000000:
        return bytes([
            0xE0 | ((value >> 24) & 0x0F),
            (value >> 16) & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF,
        ])
    else:
        return bytes([0xF0]) + struct.pack("!I", value & 0xFFFFFFFF)


def _patch_send_audio(mumble_obj) -> None:
    """Monkey-patch SendAudio.send_audio to use legacy audio format.

    The pymumble 2.0 sourcehut fork sends audio in protobuf format, but
    servers running older versions (< 1.5) only understand the legacy format:
      byte 0: (type << 5) | target   (type 4 = OPUS)
      varint: sequence number
      varint: opus_len | (terminator << 13)
      bytes:  opus payload
    """
    import socket
    from mumble.constants import TCP_MSG_TYPE

    sa = mumble_obj.send_audio
    if sa is None:
        return

    _original_send_audio = sa.send_audio

    def legacy_send_audio():
        import opuslib
        from mumble.constants import SAMPLE_RATE, SEQUENCE_DURATION, SEQUENCE_RESET_INTERVAL

        if not sa.encoder or len(sa.pcm) == 0:
            sa.queue_empty.set()
            return ()

        samples = int(sa.encoder_framesize * SAMPLE_RATE * 2 * sa.channels)

        while (
            len(sa.pcm) > 0
            and sa.sequence_last_time + sa.audio_per_packet <= time.time()
        ):
            current_time = time.time()
            if sa.sequence_last_time + SEQUENCE_RESET_INTERVAL <= current_time:
                sa.sequence = 0
                sa.sequence_start_time = current_time
                sa.sequence_last_time = current_time
            elif sa.sequence_last_time + (sa.audio_per_packet * 2) <= current_time:
                sa.sequence = int(
                    (current_time - sa.sequence_start_time) / SEQUENCE_DURATION
                )
                sa.sequence_last_time = sa.sequence_start_time + (
                    sa.sequence * SEQUENCE_DURATION
                )
            else:
                sa.sequence += int(sa.audio_per_packet / SEQUENCE_DURATION)
                sa.sequence_last_time = sa.sequence_start_time + (
                    sa.sequence * SEQUENCE_DURATION
                )

            payload = bytearray()
            audio_encoded = 0

            while len(sa.pcm) > 0 and audio_encoded < sa.audio_per_packet:
                sa.lock.acquire()
                to_encode = sa.pcm.pop(0)
                sa.lock.release()

                if len(to_encode) != samples:
                    to_encode += b"\x00" * (samples - len(to_encode))

                try:
                    encoded = sa.encoder.encode(
                        to_encode, len(to_encode) // (2 * sa.channels)
                    )
                except opuslib.exceptions.OpusError:
                    encoded = b""

                audio_encoded += sa.encoder_framesize
                payload += encoded

            sa.Log.debug(
                "audio packet to send (legacy): sequence:%d, type:OPUS, length:%d",
                sa.sequence, len(payload),
            )

            # Build legacy format packet
            # Header: (type << 5) | target — type 4 = OPUS
            header_byte = (4 << 5) | (sa.target & 0x1F)
            msg = bytes([header_byte])
            msg += _encode_varint(sa.sequence)
            # Opus header: length in bits 0-12, terminator in bit 13
            # For continuous audio, terminator = 0
            opus_header_val = len(payload) & 0x1FFF
            msg += _encode_varint(opus_header_val)
            msg += bytes(payload)

            if mumble_obj.force_tcp_only:
                tcppacket = struct.pack("!HL", TCP_MSG_TYPE.UDPTunnel, len(msg)) + msg
                while len(tcppacket) > 0:
                    sent = mumble_obj.control_socket.send(tcppacket)
                    if sent < 0:
                        raise socket.error("Server socket error")
                    tcppacket = tcppacket[sent:]
            else:
                mumble_obj.udp_thread.encrypt_and_send_message(msg)

    sa.send_audio = legacy_send_audio


class ConnectionState(enum.Enum):
    """Mumble connection state machine."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


def _user_to_dict(user) -> dict:
    """Extract user information into a plain dict."""
    info: dict = {}
    for attr in ("session", "name", "channel_id", "mute", "deaf",
                 "self_mute", "self_deaf", "suppress", "comment",
                 "priority_speaker", "recording"):
        try:
            info[attr] = getattr(user, attr, None)
        except Exception:
            pass
    return info


def _channel_to_dict(channel) -> dict:
    """Extract channel information into a plain dict."""
    info: dict = {}
    try:
        info["channel_id"] = channel.get_id()
    except Exception:
        pass
    for prop in ("name", "parent", "description", "temporary",
                 "position", "max_users"):
        try:
            info[prop] = channel.get_property(prop)
        except Exception:
            pass
    return info


class MumbleClient(QObject):
    """Manages the lifecycle of a Mumble server connection.

    Wraps pymumble 2.0 (sourcehut fork) and bridges its callbacks
    to Qt signals for thread-safe UI updates.

    Signals:
        state_changed: Emitted when connection state changes.
        audio_received: Emitted with PCM bytes from other users.
    """

    state_changed = Signal(ConnectionState)
    audio_received = Signal(bytes)
    audio_received_from_user = Signal(int, bytes)  # session_id, pcm_data

    # Auto-reconnect settings
    _RECONNECT_BASE = 1.0    # seconds
    _RECONNECT_MAX = 30.0    # seconds

    def __init__(
        self, config: ServerConfig, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._state = ConnectionState.DISCONNECTED
        self._mumble: pymumble.Mumble | None = None
        self.events = MumbleEvents()
        self._auto_reconnect = False
        self._reconnect_attempt = 0
        self._reconnect_timer: QTimer | None = None
        self._stopping = False

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    def _set_state(self, new_state: ConnectionState) -> None:
        """Update state and emit signal."""
        if self._state != new_state:
            old = self._state
            self._state = new_state
            logger.info("Connection state: %s -> %s", old.value, new_state.value)
            self.state_changed.emit(new_state)

    def connect_to_server(
        self,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
    ) -> None:
        """Initiate connection to a Mumble server.

        Parameters override the stored ServerConfig values if provided.
        """
        if self._state in (ConnectionState.CONNECTING, ConnectionState.CONNECTED):
            logger.warning("Already connected or connecting, disconnect first")
            return

        self._stopping = False
        self._auto_reconnect = True
        self._reconnect_attempt = 0

        resolved_host = host or self._config.host
        resolved_port = port or self._config.port
        resolved_user = username or self._config.username

        self._set_state(ConnectionState.CONNECTING)

        try:
            self._mumble = pymumble.Mumble(
                host=resolved_host,
                user=resolved_user,
                port=resolved_port,
                reconnect=False,  # we handle reconnect ourselves
                force_tcp_only=True,
                debug=True,
            )
            self._mumble.daemon = True

            # Patch to handle legacy audio format from older servers/clients
            _patch_sound_received(self._mumble)

            # Register pymumble callbacks -> Qt signals
            self._register_callbacks()

            # Start the pymumble thread (calls connect + loop)
            self._mumble.start()

            # Wait for connection in a background thread so we don't block Qt
            connect_thread = threading.Thread(
                target=self._wait_for_connection,
                daemon=True,
            )
            connect_thread.start()

        except Exception as exc:
            logger.exception("Failed to start Mumble connection")
            self._set_state(ConnectionState.ERROR)
            self.events.emit_error(str(exc))

    def _wait_for_connection(self) -> None:
        """Block until pymumble reports connected (runs in helper thread)."""
        try:
            if self._mumble is None:
                return
            success = self._mumble.wait_until_connected(timeout=10)
            if success:
                self._set_state(ConnectionState.CONNECTED)
                sa = self._mumble.send_audio
                if sa:
                    logger.info(
                        "Audio encoder state: codec=%s, encoder=%s, framesize=%s",
                        sa.codec, sa.encoder, sa.encoder_framesize,
                    )
                    # Patch send_audio to use legacy format for older servers
                    _patch_send_audio(self._mumble)
                    logger.info("Applied legacy send audio patch")
                else:
                    logger.warning("send_audio is None — audio disabled")
                self.events.emit_connected()
            else:
                self._set_state(ConnectionState.ERROR)
                self.events.emit_error("Connection timed out")
                self._schedule_reconnect()
        except Exception as exc:
            logger.exception("Error waiting for connection")
            self._set_state(ConnectionState.ERROR)
            self.events.emit_error(str(exc))
            self._schedule_reconnect()

    def _register_callbacks(self) -> None:
        """Wire pymumble callbacks to MumbleEvents Qt signals."""
        if self._mumble is None:
            return

        cb = self._mumble.callbacks

        cb.connected.set_handler(self._on_connected)
        cb.disconnected.set_handler(self._on_disconnected)
        cb.user_created.set_handler(self._on_user_created)
        cb.user_updated.set_handler(self._on_user_updated)
        cb.user_removed.set_handler(self._on_user_removed)
        cb.channel_created.set_handler(self._on_channel_created)
        cb.channel_updated.set_handler(self._on_channel_updated)
        cb.channel_removed.set_handler(self._on_channel_removed)
        cb.sound_received.set_handler(self._on_sound_received)

    # ---- pymumble callback handlers (run in pymumble thread) ----

    def _on_connected(self) -> None:
        logger.info("pymumble: connected")
        # The wait_for_connection thread handles the state transition

    def _on_disconnected(self) -> None:
        logger.info("pymumble: disconnected")
        if self._stopping:
            self._set_state(ConnectionState.DISCONNECTED)
            self.events.emit_disconnected()
        else:
            self._set_state(ConnectionState.ERROR)
            self.events.emit_disconnected()
            self._schedule_reconnect()

    def _on_user_created(self, user) -> None:
        self.events.emit_user_joined(_user_to_dict(user))

    def _on_user_updated(self, user, changes: dict) -> None:
        info = _user_to_dict(user)
        info["changes"] = changes
        self.events.emit_user_state_changed(info)

    def _on_user_removed(self, user, message) -> None:
        self.events.emit_user_left(_user_to_dict(user))

    def _on_channel_created(self, channel) -> None:
        self.events.emit_channel_created(_channel_to_dict(channel))

    def _on_channel_updated(self, channel, changes: dict) -> None:
        info = _channel_to_dict(channel)
        info["changes"] = changes
        self.events.emit_channel_updated(info)

    def _on_channel_removed(self, channel) -> None:
        self.events.emit_channel_removed(_channel_to_dict(channel))

    def _on_sound_received(self, user, soundchunk) -> None:
        """Receive audio from pymumble and emit as Qt signal.

        pymumble provides decoded PCM: 48kHz, 16-bit signed, mono.
        """
        pcm = soundchunk.pcm
        session = getattr(user, 'session', 0)
        logger.info("Audio received from session %d: %d bytes", session, len(pcm))
        self.events.emit_audio_received(pcm)
        self.audio_received.emit(pcm)  # keep for backward compat
        self.audio_received_from_user.emit(session, pcm)

    # ---- Reconnection logic ----

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        if self._stopping or not self._auto_reconnect:
            return

        delay = min(
            self._RECONNECT_BASE * (2 ** self._reconnect_attempt),
            self._RECONNECT_MAX,
        )
        self._reconnect_attempt += 1
        logger.info(
            "Scheduling reconnect attempt %d in %.1fs",
            self._reconnect_attempt,
            delay,
        )

        # Use a threading.Timer since we may not be on the Qt thread
        timer = threading.Timer(delay, self._do_reconnect)
        timer.daemon = True
        timer.start()

    def _do_reconnect(self) -> None:
        """Perform one reconnection attempt."""
        if self._stopping or not self._auto_reconnect:
            return

        logger.info("Attempting reconnect (attempt %d)", self._reconnect_attempt)
        # Clean up old instance
        self._cleanup_mumble()
        # Re-connect using stored config
        self.connect_to_server()

    def _cleanup_mumble(self) -> None:
        """Safely shut down the pymumble instance."""
        if self._mumble is not None:
            try:
                self._mumble.stop()
            except Exception:
                logger.debug("Error stopping mumble instance during cleanup", exc_info=True)
            self._mumble = None

    # ---- Public API ----

    def disconnect(self) -> None:
        """Disconnect from the current server."""
        self._stopping = True
        self._auto_reconnect = False
        self._cleanup_mumble()
        self._set_state(ConnectionState.DISCONNECTED)
        self.events.emit_disconnected()

    def send_audio(self, pcm_data: bytes) -> None:
        """Send PCM audio data to the server.

        Args:
            pcm_data: Raw PCM audio, 48kHz 16-bit signed mono.
        """
        if self._mumble is None or self._state != ConnectionState.CONNECTED:
            return
        if self._mumble.send_audio is None:
            return
        sa = self._mumble.send_audio
        # Wait for codec negotiation — encoder_framesize is None until
        # the server sends CodecVersion and the encoder is created.
        if sa.encoder_framesize is None:
            logger.warning(
                "Audio dropped: encoder not ready (codec=%s, encoder=%s)",
                sa.codec, sa.encoder,
            )
            return
        try:
            sa.add_sound(pcm_data)
            logger.info("add_sound: queued %d bytes", len(pcm_data))
        except Exception:
            logger.exception("Failed to send audio")

    def join_channel(self, channel_id: int) -> None:
        """Join a channel by ID."""
        if self._mumble is None or self._state != ConnectionState.CONNECTED:
            logger.warning("Cannot join channel: not connected")
            return
        try:
            channel = self._mumble.channels[channel_id]
            channel.move_in()
        except KeyError:
            logger.error("Channel %d not found", channel_id)
        except Exception:
            logger.exception("Failed to join channel %d", channel_id)

    def get_channels(self) -> dict:
        """Return the current channel tree as a dict of {id: channel_info}.

        Each channel_info dict contains: channel_id, name, parent,
        description, temporary, position, max_users.
        """
        if self._mumble is None or self._state != ConnectionState.CONNECTED:
            return {}
        result = {}
        try:
            for cid, channel in self._mumble.channels.items():
                result[cid] = _channel_to_dict(channel)
        except Exception:
            logger.exception("Failed to get channels")
        return result

    def get_users(self) -> dict:
        """Return connected users as a dict of {session: user_info}.

        Each user_info dict contains: session, name, channel_id, mute,
        deaf, self_mute, self_deaf, etc.
        """
        if self._mumble is None or self._state != ConnectionState.CONNECTED:
            return {}
        result = {}
        try:
            for session, user in self._mumble.users.by_session().items():
                result[session] = _user_to_dict(user)
        except Exception:
            logger.exception("Failed to get users")
        return result


def test_connection_cli(host: str, port: int, username: str) -> int:
    """CLI command to test server connection and exit.

    Connects to the given Mumble server, prints channels and users,
    then disconnects. Returns 0 on success, 1 on failure.
    """
    print(f"Connecting to {host}:{port} as '{username}'...")

    try:
        m = pymumble.Mumble(
            host=host,
            user=username,
            port=port,
            reconnect=False,
            force_tcp_only=True,
        )
        m.daemon = True
        m.start()

        connected = m.wait_until_connected(timeout=10)
        if not connected:
            print("ERROR: Connection timed out after 10 seconds.")
            try:
                m.stop()
            except Exception:
                pass
            return 1

        print("Connected successfully!\n")

        # Print channels
        print("Channels:")
        print("-" * 40)
        for cid, channel in sorted(m.channels.items()):
            info = _channel_to_dict(channel)
            name = info.get("name", f"<channel {cid}>")
            parent = info.get("parent", "")
            parent_str = f" (parent={parent})" if parent != "" else ""
            print(f"  [{cid}] {name}{parent_str}")

        print()

        # Print users
        print("Users:")
        print("-" * 40)
        for _session_key, user in m.users.by_session().items():
            info = _user_to_dict(user)
            name = info.get("name", "?")
            session = info.get("session", "?")
            channel_id = info.get("channel_id", "?")
            print(f"  [{session}] {name} (channel={channel_id})")

        print()
        print("Disconnecting...")
        m.stop()
        print("Done.")
        return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
