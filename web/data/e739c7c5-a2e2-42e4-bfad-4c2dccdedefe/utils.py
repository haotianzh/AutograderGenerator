import os
import shutil
import json
import stat
import yaml
import glob
import subprocess
import unittest
from pathlib import Path
from test_generator import IOTest, UnitTest
from gradescope_utils.autograder_utils.decorators import weight, visibility
from gradescope_utils.autograder_utils.json_test_runner import JSONTestRunner


class Config:
    SOURCE = '/autograder/source'
    SUBMITTED_SOURCE = '/autograder/submission'
    SUBMISSION_META_FILE = '/autograder/submission_metadata.json'
    RESULTS_FILE = '/autograder/results/results.json'
    IO_TEST_DIR = '/autograder/source/iotests'  #  directory where io tests reside
    UNIT_TEST_DIR = '/autograder/source/unittests' # directory for unit tests

ZERO_LEADERBOARD = [
    {
        'name': 'Score',
        'value': 0
    }
]

def ZERO_RESULT(msg):
    return {
        'score': 0.0,
        'stdout_visibility': 'visible',
        'output': msg,
        'leaderboard': ZERO_LEADERBOARD
    }


def BAD_FORMAT(file):
    return ZERO_RESULT('Required file not submitted: \'{0}\'.'.format(file))


def SUBMISSIONS_EXCEEDED(limit):
    return ZERO_RESULT('Exceeded maximum number of submissions: {}'.format(limit))


def NUM_SUBMISSIONS_INFO(num, limit):
    return ZERO_RESULT('Submission {} out of {}'.format(num, limit))


def file_exists(path: str) -> bool:
    return Path(path).is_file()


def is_submitted(*files: str) -> bool:
    for file in files:
        if not file_exists(os.path.join(Config.SUBMITTED_SOURCE, file)):
            return False
    return True


def write_result(**kwargs):
    with open(Config.RESULTS_FILE, 'w+') as result:
        json.dump(kwargs, result)


def write_predefined_result(file: str):
    shutil.copyfile(file, Config.RESULTS_FILE)


def number_submissions():
    '''
    :return: Number of previous submissions. On first submission, will return 0.
    '''
    with open(Config.SUBMISSION_META_FILE) as file:
        meta = json.load(file)
        return len([submission for submission in meta['previous_submissions'] if float(submission['score']) > 0])


def load_yaml(file: str):
    try:
        with open(file, 'r') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def generate_unit_test(dir_name):
    settings = load_yaml(os.path.join(Config.UNIT_TEST_DIR, dir_name, 'settings.yml'))
    def run_test():
        run_path = os.path.join(Config.UNIT_TEST_DIR, dir_name, 'run.sh')
        os.chmod(run_path, os.stat(run_path).st_mode | stat.S_IEXEC)
        subprocess.check_call(['dos2unix', 'run.sh'], cwd=os.path.join(Config.UNIT_TEST_DIR, dir_name),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.check_output(['./run.sh'], cwd=os.path.join(Config.UNIT_TEST_DIR, dir_name),
                                stderr=subprocess.STDOUT, timeout=settings.get('timeout', None))

    @weight(settings.get('weight', 1))
    @visibility(settings.get('visibility', 'hidden'))
    def wrapper(self):
        show_output = settings.get('show_output', True)
        try:
            run_test()
        except subprocess.CalledProcessError as e:  # test script returned non-zero
            msg = '{}\n\n{}'.format(settings.get('message', ''), e.output.decode() if show_output else '')
            raise Exception(msg)
        except subprocess.TimeoutExpired as e:
            msg = '{}\n\n{}'.format('Test timed out', e.output.decode() if show_output else '')
            raise Exception(msg)

    wrapper.__doc__ = '{}'.format(settings.get('name', os.path.basename(dir_name)))
    return wrapper


def build_test_class(data_dir):
    klass = IOTest(
        IOTest.klass_name(data_dir),
        (unittest.TestCase,),
        {
            'data_dir': data_dir
        }
    )
    return klass


def find_data_directories(base_dir):
    if not os.path.exists(base_dir):
        return []
    return filter(
        lambda x: os.path.isdir(os.path.join(base_dir, x)),
        os.listdir(base_dir)
    )


def run_tests(pending_messages):
    suite = unittest.TestSuite()

    # add IO tests into testsuite
    for dir in find_data_directories(Config.IO_TEST_DIR):
        klass = build_test_class(dir)
        suite.addTest(klass(IOTest.test_name(dir)))

    # add unit tests into testsuite
    for dir in find_data_directories(Config.UNIT_TEST_DIR):
        test_fn = generate_unit_test(dir)
        t = UnitTest(test_fn, (unittest.TestCase,), {})
        suite.addTest(t(test_fn.__doc__))


    with open(Config.RESULTS_FILE, 'w+') as result_stream:
        JSONTestRunner(stdout_visibility='visible', stream=result_stream).run(suite)
        result_stream.seek(0)  # reset file pointer
        data = json.load(result_stream)  # load contents to JSON
        final_score = data.get('score', 0.0)
        data['leaderboard'] = [{'name': 'Score', 'value': final_score}]

        if 'tests' not in data:
            data['tests'] = []
        for msg in pending_messages:
            data['tests'].insert(0, msg)
        result_stream.truncate(0)
        result_stream.seek(0)
        json.dump(data, result_stream)
