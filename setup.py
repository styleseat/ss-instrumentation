from setuptools import setup

setup(name='ss_instrumentation',
      version='0.1',
      description='',
      url='https://github.com/styleseat/ss-instrumentation',
      author='Some Dude at StyleSeat',
      packages=['ss_instrumentation'],
      install_requires = [
          'boto3>1',
      ],
      zip_safe=True)

