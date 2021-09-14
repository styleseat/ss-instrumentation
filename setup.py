from setuptools import (
    find_packages,
    setup,
)

setup(name='ss_instrumentation',
      version='2.0.0',
      description='',
      url='https://github.com/styleseat/ss-instrumentation',
      author='Some Dude at StyleSeat',
      packages=find_packages('src'),
      package_dir={'': 'src'},
      install_requires=['boto3>1'],
      zip_safe=True)

