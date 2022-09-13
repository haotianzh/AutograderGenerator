#!/usr/bin/env bash
#  compile test:
#  test-main.o : this is compiled in bootstrap.init and can be linked with all catch tests
#  -I ../      : indicates that there are files in the parent directory that we '#include' in our test (these are the
#                files that were submitted by the student).
#  -o <test_name> : name the compiled executable
cp /autograder/submission/a .
