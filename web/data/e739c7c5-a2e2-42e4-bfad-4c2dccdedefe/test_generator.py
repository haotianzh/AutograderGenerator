import unittest
import os
import os.path
import subprocess
from gradescope_utils.autograder_utils.decorators import weight
import yaml

IO_TEST_DIR = '/autograder/source/iotests'  # directory where io tests reside
UNIT_TEST_DIR = '/autograder/source/unittests'  # directory for unit tests
#  class used in generating unittest TestCase's
class UnitTest(type):

    def __new__(mcs, test, bases, attrs):
        attrs[test.__doc__] = test
        return super(UnitTest, mcs).__new__(mcs, test.__doc__, bases, attrs)


class IOTest(type):
    """
    Metaclass that allows generating tests based on a directory.
    """
    def __new__(cls, name, bases, attrs):
        data_dir = attrs['data_dir']
        attrs[cls.test_name(data_dir)] = cls.generate_test(data_dir)
        return super(IOTest, cls).__new__(cls, name, bases, attrs)

    @classmethod
    def generate_test(cls, dir_name):
        """ Returns a testcase for the given directory """
        command = cls.generate_command(dir_name)

        def load_test_file(path):
            full_path = os.path.join(IO_TEST_DIR, dir_name, path)
            if os.path.isfile(full_path):
                with open(full_path, 'rb') as f:
                    return f.read()
            return None

        def load_settings():
            settings_yml = load_test_file('settings.yml')

            if settings_yml is not None:
                return yaml.safe_load(settings_yml) or {}
            else:
                return {}

        settings = load_settings()


        @weight(settings.get('weight', 1))
        def fn(self):
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdin = load_test_file('input')
            output, err = proc.communicate(stdin, settings.get('timeout', 1))
            expected_output = load_test_file('output')
            expected_err = load_test_file('err')
            msg = settings.get('msg', "Output does not match expected")
            msg = f'{msg}:\n{err}'
            self.assertEqual(expected_output, output, msg=msg)
            if expected_err is not None:
                self.assertEqual(expected_err, err, msg="Error doesn't match expected error")

        fn.__doc__ = 'Test {0}'.format(dir_name)
        return fn

    @staticmethod
    def generate_command(dir_name):
        """Generates the command passed to Popen"""
        test_specific_script = os.path.join(IO_TEST_DIR, dir_name, 'run.sh')
        if os.path.isfile(test_specific_script):
            return ["bash", test_specific_script]
        return ["bash", "./run.sh"]

    @staticmethod
    def klass_name(dir_name):
        return 'Test{0}'.format(''.join([x.capitalize() for x in dir_name.split('_')]))

    @staticmethod
    def test_name(dir_name):
        return 'test_{0}'.format(dir_name)


