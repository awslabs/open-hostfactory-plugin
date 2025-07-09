"""Setup configuration for the Open Host Factory Plugin package."""
import os
import sys
from setuptools import setup, find_packages

def get_version():
    """Get version from src/__init__.py without importing the module."""
    version_file = os.path.join(os.path.dirname(__file__), 'src', '__init__.py')
    with open(version_file, 'r') as f:
        for line in f:
            if line.startswith('__version__'):
                return line.split('=')[1].strip().strip('"').strip("'")
    raise RuntimeError("Unable to find version string.")

def get_author():
    """Get author from src/__init__.py without importing the module."""
    version_file = os.path.join(os.path.dirname(__file__), 'src', '__init__.py')
    with open(version_file, 'r') as f:
        for line in f:
            if line.startswith('__author__'):
                return line.split('=')[1].strip().strip('"').strip("'")
    return "AWS Professional Services"

def get_email():
    """Get email from src/__init__.py without importing the module."""
    version_file = os.path.join(os.path.dirname(__file__), 'src', '__init__.py')
    with open(version_file, 'r') as f:
        for line in f:
            if line.startswith('__email__'):
                return line.split('=')[1].strip().strip('"').strip("'")
    return "aws-proserve@amazon.com"

# Read requirements
with open('requirements.txt') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Read development requirements
with open('requirements-dev.txt') as f:
    dev_requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Read long description
with open('README.md', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='open-hostfactory-plugin',
    version=get_version(),
    description='Open Host Factory Plugin for IBM Spectrum Symphony',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author=get_author(),
    author_email=get_email(),
    url='https://github.com/aws-samples/awsome-hostfactory-plugin',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    python_requires='>=3.8',
    install_requires=requirements,
    extras_require={
        'dev': dev_requirements,
        'test': [
            'pytest>=7.4.3',
            'pytest-cov>=4.1.0',
            'pytest-env>=1.1.1',
            'pytest-mock>=3.12.0',
            'pytest-asyncio>=0.21.1',
            'pytest-timeout>=2.2.0',
            'coverage>=7.3.2',
            'moto>=4.2.7',
        ],
        'docs': [
            'mkdocs>=1.5.0',
            'mkdocs-material>=9.1.0',
            'mkdocstrings>=0.22.0',
            'mkdocstrings-python>=1.1.0',
            'mkdocs-gen-files>=0.5.0',
            'mkdocs-literate-nav>=0.6.0',
            'mkdocs-section-index>=0.3.0',
            'mike>=1.1.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'ohfp=run:main',
            'open-hostfactory-plugin=run:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Clustering',
        'Topic :: System :: Distributed Computing',
    ],
    keywords=[
        'aws',
        'ec2',
        'hostfactory',
        'symphony',
        'hpc',
        'cluster',
        'cloud',
        'infrastructure',
    ],
    project_urls={
        'Bug Reports': 'https://github.com/aws-samples/awsome-hostfactory-plugin/issues',
        'Source': 'https://github.com/aws-samples/awsome-hostfactory-plugin',
        'Documentation': 'https://awsome-hostfactory-plugin.readthedocs.io/',
    },
    zip_safe=False,
    test_suite='tests',
)
