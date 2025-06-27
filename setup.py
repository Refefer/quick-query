import setuptools

setuptools.setup(
    name="quick-query",
    version="0.1",
    packages=setuptools.find_packages(),
    entry_points={
        "console_scripts": [
            "qq = quick_query.cli:cli_entrypoint",
        ],
    },
    install_requires=[
        "requests>=2.31"
    ],
    extras_require={
        "markdown": ["rich"],
        "template": ["Jinja2>=3.1"]
    },
    author="Andrew Stanton",
    author_email="refefer@gmail.com",
    description="A very lightweight terminal llm chat and prompter.",
    url="https://github.com/refefer/quick-query",
    license="MIT",
)
