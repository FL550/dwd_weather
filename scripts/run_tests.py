#!/usr/bin/env python3
"""
Test runner for DWD Weather component
Provides easy CLI interface to run different test suites
"""

import subprocess
import sys
import argparse
from pathlib import Path


class Colors:
    """ANSI color codes"""

    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"  # No Color


def print_header(text: str) -> None:
    """Print a formatted header"""
    print(f"{Colors.BLUE}{'='*40}{Colors.NC}")
    print(f"{Colors.BLUE}{text}{Colors.NC}")
    print(f"{Colors.BLUE}{'='*40}{Colors.NC}")


def print_success(text: str) -> None:
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.NC}")


def print_error(text: str) -> None:
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.NC}")


def print_info(text: str) -> None:
    """Print info message"""
    print(f"{Colors.YELLOW}ℹ {text}{Colors.NC}")


def run_command(cmd: list, description: str = "") -> int:
    """Run a shell command and return exit code"""
    if description:
        print_header(description)

    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
        return result.returncode
    except FileNotFoundError:
        print_error(f"Command not found: {cmd[0]}")
        return 1


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Test runner for DWD Weather component",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s all                              # Run all tests
  %(prog)s coverage                         # Generate coverage report
  %(prog)s config                          # Run configuration tests only
  %(prog)s specific tests/test_config_flow.py  # Run specific test file
        """,
    )

    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=[
            "all",
            "unit",
            "integration",
            "quick",
            "coverage",
            "config",
            "entities",
            "verbose",
            "lint",
            "format",
            "specific",
        ],
        help="Test command to run",
    )

    parser.add_argument(
        "target",
        nargs="?",
        help="Target for 'specific' command (test file or function name)",
    )

    args = parser.parse_args()

    commands = {
        "all": (
            [
                "pytest",
                "--cov=custom_components/dwd_weather",
                "--cov-report=html",
                "--cov-report=term-missing",
            ],
            "Running All Tests",
        ),
        "unit": (
            ["pytest", "tests/test_connector.py", "tests/test_config_flow.py", "-v"],
            "Running Unit Tests",
        ),
        "integration": (
            ["pytest", "tests/test__init.py", "-v"],
            "Running Integration Tests",
        ),
        "quick": (["pytest", "-x", "--tb=short"], "Running Quick Test Suite"),
        "coverage": (
            [
                "pytest",
                "--cov=custom_components/dwd_weather",
                "--cov-report=html",
                "--cov-report=term-missing",
            ],
            "Running Tests with Coverage Report",
        ),
        "config": (
            ["pytest", "tests/test_config_flow.py", "-v"],
            "Running Config Flow Tests",
        ),
        "entities": (
            [
                "pytest",
                "tests/test_weather_entity.py",
                "tests/test_sensor_entity.py",
                "-v",
            ],
            "Running Entity Tests",
        ),
        "verbose": (["pytest", "-v", "--tb=long"], "Running All Tests (Verbose)"),
        "lint": (
            ["ruff", "check", "custom_components/dwd_weather", "tests"],
            "Running Linters",
        ),
        "format": (
            ["ruff", "format", "custom_components/dwd_weather", "tests"],
            "Formatting Code",
        ),
    }

    if args.command == "specific":
        if not args.target:
            print_error("Please provide test path or name for 'specific' command")
            print_info("Usage: run_tests.py specific <test_path_or_name>")
            print_info("Example: run_tests.py specific tests/test_config_flow.py")
            sys.exit(1)

        cmd = ["pytest", args.target, "-v"]
        exit_code = run_command(cmd, f"Running Specific Test: {args.target}")
    else:
        if args.command not in commands:
            print_error(f"Unknown command: {args.command}")
            parser.print_help()
            sys.exit(1)

        cmd, description = commands[args.command]
        exit_code = run_command(cmd, description)

    if exit_code == 0:
        print_success("Tests passed!")

        # Show coverage report location for coverage command
        if args.command == "coverage":
            print_info("Coverage report generated in htmlcov/index.html")
    else:
        print_error("Tests failed!")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
