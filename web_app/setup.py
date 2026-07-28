from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="nl2sparql",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Natural Language to SPARQL Query Translation Framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/nl2sparql",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "nl2sparql=nl2sparql.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "nl2sparql": ["*.yaml"],
    },
    keywords="sparql nlp knowledge-graph semantic-web rdf shacl question-answering",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/nl2sparql/issues",
        "Source": "https://github.com/yourusername/nl2sparql",
        "Documentation": "https://github.com/yourusername/nl2sparql#readme",
    },
)
