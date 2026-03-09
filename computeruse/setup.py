"""
setup.py — Package distribution configuration for the ComputerUse SDK.

Prefer using 'pip install .' (PEP 517 / pyproject.toml) for new projects.
This file is retained for compatibility with tools that do not yet support
PEP 517 builds (e.g. older pip versions, certain CI environments).
"""

from pathlib import Path

from setuptools import find_packages, setup

# ---------------------------------------------------------------------------
# Read metadata from package source so there is a single source of truth.
# ---------------------------------------------------------------------------

# Grab __version__ without importing the package (avoids triggering imports
# of heavy dependencies that may not be installed yet at build time).
_version_file = Path(__file__).parent / "computeruse" / "__init__.py"
_version = "0.1.0"
for line in _version_file.read_text(encoding="utf-8").splitlines():
    if line.startswith("__version__"):
        _version = line.split("=", 1)[1].strip().strip('"').strip("'")
        break

long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Core runtime dependencies.
# Keep in sync with pyproject.toml [tool.poetry.dependencies].
# ---------------------------------------------------------------------------

install_requires = [
    "anthropic>=0.40.0",
    "browser-use>=1.0.0",
    "playwright>=1.40.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.0.0",
    "click>=8.1.0",
    "rich>=13.7.0",
    "python-dotenv>=1.0.0",
    "Pillow>=10.0.0",
    "aiohttp>=3.9.0",
    "httpx>=0.26.0",
    "langchain-anthropic>=0.1.0",
]

extras_require = {
    # Backend services (not required for local SDK use).
    "backend": [
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "celery>=5.3.0",
        "redis>=5.0.0",
        "asyncpg>=0.29.0",
        "aioboto3>=12.0.0",
        "boto3>=1.34.0",
        "requests>=2.31.0",
    ],
    # Development and testing.
    "dev": [
        "pytest>=8.0.0",
        "pytest-asyncio>=0.23.0",
        "black>=24.0.0",
        "mypy>=1.8.0",
        "ruff>=0.2.0",
    ],
    # Convenience: install everything.
    "all": [],  # populated below
}
extras_require["all"] = list(
    {dep for group in extras_require.values() for dep in group}
)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup(
    # ── Identity ──────────────────────────────────────────────────────────
    name="computeruse",
    version=_version,
    description="One API to automate any web workflow",
    long_description=long_description,
    long_description_content_type="text/markdown",

    # ── Author ────────────────────────────────────────────────────────────
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/your-org/computeruse",
    project_urls={
        "Documentation": "https://docs.computeruse.dev",
        "Bug Tracker":   "https://github.com/your-org/computeruse/issues",
        "Changelog":     "https://github.com/your-org/computeruse/releases",
    },

    # ── Packages ──────────────────────────────────────────────────────────
    packages=find_packages(exclude=["tests*", "examples*", "docs*"]),
    include_package_data=True,   # picks up files listed in MANIFEST.in

    # ── Dependencies ──────────────────────────────────────────────────────
    python_requires=">=3.10",
    install_requires=install_requires,
    extras_require=extras_require,

    # ── CLI entry point ───────────────────────────────────────────────────
    entry_points={
        "console_scripts": [
            "computeruse=computeruse.cli.main:cli",
        ],
    },

    # ── PyPI classifiers ──────────────────────────────────────────────────
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3 :: Only",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    ],
    keywords=[
        "browser automation", "web scraping", "ai agent",
        "playwright", "anthropic", "computer use", "rpa",
    ],
)
