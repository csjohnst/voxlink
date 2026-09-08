"""VoxLink entry point."""

from __future__ import annotations

import argparse
import logging
import sys

from voxlink import __version__


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="voxlink",
        description="VoxLink — Wayland-native Mumble voice chat client",
    )
    parser.add_argument("--version", action="version", version=f"VoxLink {__version__}")
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test connection to a Mumble server and exit",
    )
    parser.add_argument("--server", type=str, help="Mumble server hostname")
    parser.add_argument("--user", type=str, help="Username for server connection")
    parser.add_argument("--port", type=int, default=64738, help="Server port")
    parser.add_argument(
        "--cert",
        type=str,
        help="Client certificate (PEM) for --test-connection; defaults to config certfile",
    )
    parser.add_argument(
        "--key",
        type=str,
        help="Private key (PEM) for --cert; defaults to config keyfile",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio devices and exit",
    )
    parser.add_argument(
        "--test-ptt",
        action="store_true",
        help="Test push-to-talk shortcut detection and exit",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to config file",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    return parser.parse_args()


def setup_logging(verbose: bool) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    """Main entry point for VoxLink."""
    args = parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger("voxlink")

    if args.list_devices:
        from voxlink.audio.devices import list_devices_cli

        return list_devices_cli()

    if args.test_connection:
        if not args.server or not args.user:
            logger.error("--test-connection requires --server and --user")
            return 1
        from pathlib import Path

        from voxlink.config import VoxLinkConfig
        from voxlink.mumble.client import test_connection_cli

        cfg = VoxLinkConfig.load(Path(args.config) if args.config else None)
        certfile = args.cert or cfg.server.certfile or None
        keyfile = args.key or cfg.server.keyfile or None
        return test_connection_cli(args.server, args.port, args.user, certfile, keyfile)

    if args.test_ptt:
        from voxlink.shortcuts.manager import test_ptt_cli

        return test_ptt_cli()

    # Launch the GUI
    from voxlink.app import run_app

    return run_app(config_path=args.config)


if __name__ == "__main__":
    sys.exit(main())
