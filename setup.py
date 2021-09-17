from setuptools import (
    find_packages,
    setup,
)

from src.ss_instrumentation import (
    __version__,
)

setup(
    name="ss_instrumentation",
    version=__version__,
    description=(
        "A light wrapper around the boto3 cloudwatch client intended for reporting custom metrics to cloudwatch."
    ),
    url="https://github.com/styleseat/ss-instrumentation",
    author="StyleSeat Engineering",
    packages=find_packages("src"),
    package_dir={"": "src"},
    install_requires=["boto3>1"],
    zip_safe=True,
)
