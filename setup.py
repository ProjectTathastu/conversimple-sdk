"""
Setup configuration for Conversimple Python SDK (conversimple-sdk package name).

This SDK enables customers to build and deploy AI agents that integrate with
the Conversimple platform's WebRTC infrastructure and conversation management.
"""

from setuptools import setup, find_packages

# Read README for long description
try:
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
except FileNotFoundError:
    long_description = "Conversimple SDK - Python client library for the Conversational AI Platform"

setup(
    name="conversimple-sdk",
    version="0.2.0",  # Enhanced connection resilience with circuit breaker
    author="Conversimple",
    author_email="support@conversimple.com",
    description="Python SDK for Conversimple Conversational AI Platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/conversimple/conversimple-sdk",
    project_urls={
        "Bug Tracker": "https://github.com/conversimple/conversimple-sdk/issues",
        "Documentation": "https://docs.conversimple.com/sdk",
        "Platform": "https://platform.conversimple.com",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Communications :: Chat",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "websockets>=12.0",
        "aiofiles>=23.0",
        "aiohttp>=3.8.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0",
            "flake8>=6.0",
            "mypy>=1.0",
        ],
        "examples": [
            "aiofiles>=23.0",
            "aiohttp>=3.8.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "conversimple-example=examples.simple_agent:main",
        ],
    },
    keywords="conversational ai, voice ai, chatbot, websocket, sdk, speech to text, text to speech",
    zip_safe=False,
)
