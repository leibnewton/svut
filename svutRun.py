#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright 2022 The SVUT Authors

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# pylint: disable=W0621

import os
import sys
import argparse
import filecmp
import subprocess
import datetime
from timeit import default_timer as timer
from datetime import timedelta

SCRIPTDIR = os.path.abspath(os.path.dirname(__file__))


def find_unit_tests():
    """
    Parse all unit test files of the current folder
    and return a list of available tests
    """

    supported_prefix = ["tb_", "ts_", "testbench_", "testsuite_", "unit_test_"]
    supported_suffix = ["_unit_test.v", "_unit_test.sv",
                        "_testbench.v", "_testbench.sv",
                        "_testsuite.v", "_testsuite.sv",
                        "_tb.v", "_tb.sv", "_ts.v", "_ts.sv"]
    files = []
    # Parse the current folder
    for _file in os.listdir(os.getcwd()):
        # Check only the files
        if os.path.isfile(_file):
            for suffix in supported_suffix:
                if _file.endswith(suffix):
                    files.append(_file)
            for prefix in supported_prefix:
                if _file.startswith(prefix):
                    files.append(_file)
    # Remove duplicated file if contains both prefix and suffix
    files = list(set(files))
    return files


def get_defines(defines):
    """
    Return a string with the list of defines ready to drop in icarus
    """
    simdefs = ""

    if not defines:
        return simdefs

    defs = defines.split(';')

    for _def in defs:
        if _def:
            simdefs += "-D" + _def + " "

    return simdefs


def create_iverilog(args, test):
    """
    Create the Icarus Verilog command to launch the simulation
    """
    # Remove the compiled file if it exists. That ensures that a compilation
    # won't run an obsolete test.
    cmds = ["rm -f icarus.out"]
    cmd = "iverilog -g2012 -Wall -o icarus.out "

    if args.define:
        cmd += get_defines(args.define)

    if args.dotfile:

        dotfiles = ""

        for dot in args.dotfile:
            if os.path.isfile(dot):
                dotfiles += dot + " "

        if dotfiles:
            cmd += "-f " + dotfiles + " "

    if args.include:
        incs = " ".join(args.include)
        cmd += "-I " + incs + " "

    cmd += test + " "

    # Check the extension and extract test name
    if test[-2:] != ".v" and test[-3:] != ".sv":
        print("ERROR: failed to find supported extension. \
               Must use either *.v or *.sv")
        sys.exit(1)

    cmds.append(cmd)

    cmd = "vvp "
    if args.vpi:
        cmd += args.vpi + " "
    cmd += "icarus.out "

    if args.gui:
        cmd += "-lxt;"
    cmds.append(cmd)

    if args.gui:
        if os.path.isfile("wave.gtkw"):
            cmds.append("gtkwave *.lxt wave.gtkw &")
        else:
            cmds.append("gtkwave *.lxt &")

    return cmds


def create_verilator(args, test):
    """
    Create the Verilator command to launch the simulation
    """

    testname = os.path.basename(test).split(".")[0]

    cmds = ["rm -fr build"]
    # build compilation command
    cmd = """verilator -Wall --trace --Mdir build +1800-2017ext+sv """
    cmd += """+1800-2005ext+v -Wno-STMTDLY -Wno-UNUSED -Wno-UNDRIVEN -Wno-PINCONNECTEMPTY """
    cmd += """-Wpedantic -Wno-VARHIDDEN -Wno-lint """

    if args.define:
        cmd += get_defines(args.define)

    if args.dotfile:

        dotfiles = ""

        for dot in args.dotfile:
            if os.path.isfile(dot):
                dotfiles += dot + " "

        if dotfiles:
            cmd += "-f " + dotfiles + " "

    if args.include:
        for inc in args.include:
            cmd += "+incdir+" + inc + " "

    # Check the extension and extract test name
    if test[-2:] != ".v" and test[-3:] != ".sv":
        print("ERROR: failed to find supported extension. \
               Must use either *.v or *.sv")
        sys.exit(1)

    cmd += "-cc --exe --build -j --top-module " + testname + " "
    cmd += test + " " + args.main
    cmds.append(cmd)

    # Build execution command
    cmd = "make -j -C build -f V" + testname + ".mk V" + testname
    cmds.append(cmd)
    cmd = "build/V" + testname
    cmds.append(cmd)

    return cmds


def print_event(event, git_tag):
    """
    Print an event during SVUT execution
    """

    print("")
    print("------------------------------------------------")
    print("SVUT " + git_tag)
    print(event + " @ " + datetime.datetime.now().time().strftime('%H:%M:%S'))
    print("------------------------------------------------")
    print("")
    return 0


def get_git_tag():
    """
    Return current SVUT version
    """

    file_path = os.path.dirname(os.path.abspath(__file__))
    curr_path = os.getcwd()
    os.chdir(file_path)

    try:
        git_tag = subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"])
        git_tag = git_tag.strip().decode('ascii')
    except:
        print("WARNING: Can't get last git tag. Will return v0.0.0")
        git_tag = "v0.0.0"

    os.chdir(curr_path)
    return git_tag


if __name__ == '__main__':

    PARSER = argparse.ArgumentParser(description='SystemVerilog Unit Test')

    PARSER.add_argument('-test', dest='test', type=str,
                        default="all", nargs="*",
                        help='Unit test to run. A file or a list of files')

    PARSER.add_argument('-f', dest='dotfile', type=str, default=["files.f"],
                        nargs="*",
                        help="A dot file (*.f) with incdir, define and files")

    PARSER.add_argument('-sim', dest='simulator', type=str,
                        default="icarus",
                        help='The simulator to use.')

    PARSER.add_argument('-main', dest='main', type=str,
                        default="sim_main.cpp",
                        help='Verilator main cpp file')

    PARSER.add_argument('-define', dest='define', type=str,
                        default="",
                        help='''A list of define separated by ;\
                              ex: -define "DEF1=2;DEF2;DEF3=3"''')

    PARSER.add_argument('-vpi', dest='vpi', type=str,
                        default="",
                        help='''A string of arguments passed as is to icarus, separated by a space\
                              ex: -vpi "-M. -mMyVPI"''')

    PARSER.add_argument('-gui', dest='gui',
                        action='store_true',
                        help='Active the lxt dump and open GTKWave')

    PARSER.add_argument('-dry-run', dest='dry',
                        action='store_true',
                        help='Just print the command, don\'t execute. \
                                For debug purpose only.')

    PARSER.add_argument('-include', dest='include', type=str, nargs="*",
                        default="", help='Specify an include folder')

    ARGS = PARSER.parse_args()

    if ARGS.test == "all":
        ARGS.test = find_unit_tests()

    for tests in ARGS.test:

        # Lower the simulator name to ease process
        ARGS.simulator = ARGS.simulator.lower()

        if "iverilog" in ARGS.simulator or "icarus" in ARGS.simulator:
            CMDS = create_iverilog(ARGS, tests)

        elif "verilator" in ARGS.simulator:
            CMDS = create_verilator(ARGS, tests)

        else:
            print("ERROR: Simulator not supported. Icarus is the only option")
            sys.exit(1)

        # First copy svut_h.sv macro in the user folder if not present or different
        org_hfile = SCRIPTDIR + "/svut_h.sv"
        curr_hfile = os.getcwd() + "/svut_h.sv"

        if (not os.path.isfile(curr_hfile)) or\
                (not filecmp.cmp(curr_hfile, org_hfile)):
            print("INFO: Copy newest version of svut_h.sv")
            os.system("cp " + org_hfile + " " + os.getcwd())

        # Get git tag to print it during status
        GIT_TAG = get_git_tag()

        # Don't execute command, just print them for debug purpose
        if ARGS.dry:
            print("SVUT " + GIT_TAG + " dry-run: ")
            print(CMDS, flush=True)
            sys.exit(0)

        start = timer()
        print_event("Start", GIT_TAG)

        cmdret = 0
        # Execute commands one by one
        for CMD in CMDS:
            print(CMD, flush=True)
            cmdret = os.system(CMD)
            if cmdret:
                cmdret = 1
                print("ERROR: Command failed: " + CMD)
                break

        end = timer()
        print("Elapsed time:", timedelta(seconds=end-start))

        print_event("Stop", GIT_TAG)
        sys.exit(cmdret)
