import sys
sys.path.append('data/static')
import os
import posixpath
import re
import uuid
import shutil
import flask
from flask import Flask, render_template, request, redirect, make_response
from data.static.utils import Config
app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
UPLOAD_FOLDER = 'data/'
users = {}

class User(object):
    def __init__(self, uid):
        self.uid = uid
        self.num_cases = -1
        self.test_cases = []
        self.num_submissions = 0
        self.submissions = []
        self.displayed_submissions = ''
        self.limit_times = -1


class Submission(object):
    def __init__(self, name, compile_command, execute_command):
        self.name = name
        self.compile_command = compile_command
        self.execute_command = execute_command


class Case(object):
    def __init__(self, name, point, test_for):
        self.name = name
        self.point = point
        self.test_for = test_for


class IOCase(Case):
    def __init__(self, name, point, test_for, test_in, test_out):
        super().__init__(name, point, test_for)
        self.test_in = test_in
        self.test_out = test_out


class UnitCase(Case):
    def __init__(self, name, point, test_for, test_code, run_code):
        super().__init__(name, point, test_for)
        self.test_code = test_code
        self.run_code = run_code


@app.route("/")
def home():
    global users
    uid = str(uuid.uuid4())
    users[uid] = User(uid)
    response = make_response(render_template("index.html",num_cases=0, user=users[uid]))
    response.set_cookie('uid', uid)
    return response


@app.route('/init', methods=['GET', 'POST'])
def init():
    global users
    print(list(users.keys()))
    uid = request.cookies['uid']
    if not uid == '' and uid is not None and uid in users:
        user = users[uid]
        if user.num_cases == -1:
            num_cases = request.form.get('num_cases')
            if num_cases.isdigit():
                num_cases = int(num_cases)
                user.num_cases = num_cases
        if not user.submissions:
            submissions = get_submission_specs(request.form['submissions'])
            if not type(submissions) == str:
                user.submissions = submissions
            else:
                return back_to_previous(submissions, 'home')
            user.displayed_submissions = request.form.get('submissions')
            user.num_submissions = len(user.submissions)
    else:
        return back_to_previous('build the docker from the beginning', 'home')
    return render_template("index.html", user=user, show_test=True)


@app.route('/add-unit-test', methods=['GET'])
def add_unit_test():
    html = '<p> hello ajax! </p>'
    return


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    global users
    user = users[request.cookies['uid']]
    # get all cases
    if request.method == 'POST':
        case_names = set()
        form = request.form
        files = request.files
        save_static(user, files.getlist('static'))
        for i in range(user.num_cases):
            name = form[f'test_name_{i}']
            point = form[f'test_weight_{i}']
            test_for = form[f'test_for_{i}']
            test_type = form[f'test_type_{i}']
            # check filename and duplication
            if name.strip() == '':
                return back_to_previous('case name is empty', 'init')
            if name not in case_names:
                case_names.add(name)
            else:
                return back_to_previous('case name duplicated', 'init')
            # save cases
            if test_type == 'io':
                test_in = files[f'test_input_{i}']
                test_out = files[f'test_output_{i}']
                if test_in.filename.strip() == '' or test_out.filename.strip() == '':
                    return back_to_previous('input /or output can not be none', 'init')
                case = IOCase(name, point, test_for, test_in, test_out)
                user.test_cases.append(case)
            else:
                test_code = form[f'editor_{i}']
                run_code = form[f'run_{i}']
                print('run code', run_code)
                case = UnitCase(name, point, test_for, test_code, run_code)
                user.test_cases.append(case)
        # build IO tests and unit tests
        build(user)
    return render_template("index.html", user=user, download=True, download_url=f'static/{user.uid}.zip')


def build_io_test():
    pass


def build_unit_test():
    pass


def back_to_previous(msg, endpoint):
    flask.flash(msg)
    return redirect(app.url_for(endpoint))


def save_static(user, files):
    if files:
        make_dirs(os.path.join(UPLOAD_FOLDER, user.uid, 'static'))
        for file in files:
            file.save(os.path.join(UPLOAD_FOLDER, user.uid, 'static', file.filename))


def get_submission_specs(submissions_str):
    submissions = []
    submissions_str = submissions_str.split('\n')
    for submission_str in submissions_str:
        submission_str = submission_str.strip()
        specs = submission_str.split('|')
        if len(specs) > 2:
            return 'incorrect submission information'
        if len(specs) == 2:
            name, compile_cmd = (val.strip() for val in specs)
            # generate executing command by default for C++ `g++ xxx -o xxx ...`
            execute_cmd_finder = re.findall(r'-o (\S+)', compile_cmd)
            if execute_cmd_finder:
                execute_cmd = f'{Config.SOURCE}/{execute_cmd_finder[0]}'
            else:
                return 'compiled output not specified'
            submission = Submission(name=name, compile_command=compile_cmd, execute_command=execute_cmd)
            print(name, compile_cmd, execute_cmd)
            submissions.append(submission)
        elif len(specs) == 1:
            name = specs[0].strip()
            submission = Submission(name=name, compile_command='', execute_command='')
            print(name, '', '')
            submissions.append(submission)
    return submissions        


def find_submission(user, name):
    for submission in user.submissions:
        if name == submission.name:
            return submission


def create_compile_file(specs):
    file_formatted = f'#!/usr/bin/env bash\ncd {Config.SOURCE}\n'
    for spec in specs:
        # file_formatted += '# copy submissions to the source folder\n'
        # file_formatted += f'cp {Config.SUBMITTED_SOURCE}/{spec.name} {Config.SOURCE}/{spec.name}\n'
        file_formatted += '# compile submissions\n'
        file_formatted += f'{spec.compile_command}\n'
    return file_formatted


def create_run_sh_file(execute_cmd, input_file):
    file_formatted = f'#!/usr/bin/env bash\n{execute_cmd} {input_file}'
    return file_formatted


def create_config_file(user):
    file_formatted = f'limit_submissions: {user.limit_times}\nrequired_files:\n'
    for submission in user.submissions:
        file_formatted += f'  - {submission.name}\n'
    return file_formatted


def create_settings_file(weight=1, msg='', show_output=True, visibility='hidden'):
    settings = {'weight': weight,
            'msg': msg,
            'show_output': show_output,
            'visibility': visibility}
    file_formatted = ''
    for key, value in settings.items():
        file_formatted += f'{key}: {value}\n'
    return file_formatted


def make_dirs(path):
    if not os.path.exists(path):
        os.makedirs(path)
        

def build_all_files(user):
    # generate `compile.sh`
    make_dirs(os.path.join(UPLOAD_FOLDER, user.uid))
    
    with open(os.path.join(UPLOAD_FOLDER, user.uid, 'compile.sh'), 'w') as out:
        out.write(create_compile_file(user.submissions))
    # generate `config.yaml`
    with open(os.path.join(UPLOAD_FOLDER, user.uid, 'config.yaml'), 'w') as out:
        out.write(create_config_file(user))

    # copy libs
    os.system(f'cp {UPLOAD_FOLDER}/static/setup.sh {UPLOAD_FOLDER}/{user.uid}/setup.sh')
    os.system(f'cp {UPLOAD_FOLDER}/static/test_generator.py {UPLOAD_FOLDER}/{user.uid}/test_generator.py')
    os.system(f'cp {UPLOAD_FOLDER}/static/setup.sh {UPLOAD_FOLDER}/{user.uid}/setup.sh')
    os.system(f'cp {UPLOAD_FOLDER}/static/utils.py {UPLOAD_FOLDER}/{user.uid}/utils.py')
    os.system(f'cp {UPLOAD_FOLDER}/static/run_autograder {UPLOAD_FOLDER}/{user.uid}/run_autograder')
    os.system(f'cp {UPLOAD_FOLDER}/static/requirements.txt {UPLOAD_FOLDER}/{user.uid}/requirements.txt')

    # save io test cases into folders for backing up
    for case in user.test_cases:
        if isinstance(case, IOCase):
            make_dirs(os.path.join(UPLOAD_FOLDER, user.uid, 'iotests', case.name))
            case.test_in.save(os.path.join(UPLOAD_FOLDER, user.uid, 'iotests', case.name, 'input'))
            case.test_out.save(os.path.join(UPLOAD_FOLDER, user.uid, 'iotests', case.name, 'output'))
            # create `run.sh`
            with open(os.path.join(UPLOAD_FOLDER, user.uid, 'iotests', case.name, 'run.sh'), 'w') as out:
                out.write(create_run_sh_file(find_submission(user, case.test_for).execute_command, posixpath.join(Config.SOURCE, 'iotests', case.name, 'input')))
            # create `settings.yaml`
            with open(os.path.join(UPLOAD_FOLDER, user.uid, 'iotests', case.name, 'settings.yaml'), 'w') as out:
                out.write(create_settings_file(weight=case.point, msg=f'Faild to correctly run {case.test_for}'))
        if isinstance(case, UnitCase):
            make_dirs(os.path.join(UPLOAD_FOLDER, user.uid, 'unittests', case.name))
            # create `run.sh` file
            with open(os.path.join(UPLOAD_FOLDER, user.uid, 'unittests', case.name, 'run.sh'), 'w') as out:
                for line in case.run_code.split('\n'):
                    line = line.rstrip()
                    if line:
                        out.write(line)
                        out.write('\n')
            # create `test.cpp` file
            with open(os.path.join(UPLOAD_FOLDER, user.uid, 'unittests', case.name, 'test.cpp'), 'w') as out:
                for line in case.test_code.split('\n'):
                    line = line.rstrip()
                    if line:
                        out.write(line)
                        out.write('\n')
            # create `settings.yaml`
            with open(os.path.join(UPLOAD_FOLDER, user.uid, 'unittests', case.name, 'settings.yaml'), 'w') as out:
                out.write(create_settings_file(weight=case.point, msg=f'Faild to correctly run {case.test_for}'))
            # cp catch related files
            os.system(f'cp {UPLOAD_FOLDER}/static/makefile {UPLOAD_FOLDER}/{user.uid}/unittests')
            os.system(f'cp {UPLOAD_FOLDER}/static/test-main.cpp {UPLOAD_FOLDER}/{user.uid}/unittests')


def build(user):
    # create files
    build_all_files(user)
    # create a zip file `./autograder.zip`
    shutil.make_archive(f'static/{user.uid}', root_dir=f'{UPLOAD_FOLDER}/{user.uid}',  base_dir='.', format='zip')


# for security group, only support 5000 on AWS
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)