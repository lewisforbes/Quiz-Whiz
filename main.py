# Gets arguments from user, runs program, prints progress/summary.

## Ensure user has run from terminal. Assume they have on linux.
import os
from sys import exit

if os.name == 'nt' and not 'SESSIONNAME' in os.environ:
    # running from windows gui
    print("Error: program must be ran from the command line.")
    print("\nTo do this:")
    print("1. Press Win + R")
    print("2. Type cmd. Press Enter")
    print(f"3. Type cd {os.path.dirname(os.path.abspath(__file__))}. Press Enter")
    print("4. Type python3 main.py. Press Enter.")
    input("\nPress enter to exit...\n")
    exit()

#####################
## MODULES/IMPORTS ##
#####################
# Test user has required modules installed. Prompt them to install if not.
def init_nonstd_modules():
    import tabulate
    import pypandoc
    import colorama

try:
    init_nonstd_modules()
except ModuleNotFoundError:
    import subprocess
    from program.utils import get_user_input

    packages = ["tabulate", "pypandoc", "colorama"]
    if not get_user_input(f"Missing required package(s).\nInstall following with Pip: {str(packages)[1:-1]}?"):
        # find which packages must be installed
        missing = []
        for p in packages:
            try:
                exec(f"import {p}")
            except ModuleNotFoundError:
                missing.append(p)
        
        s = "" if len(missing)==1 else "s"
        print(f"\nMissing following package{s}: {str(missing)[1:-1]}. Exiting...")
        exit()

    print("Installing packages...", end=" ", flush=True)
    # user has opted to install packages
    # check if pip(3) is installed
    for p in ["pip", "pip3"]:
        try:
            pip = p
            subprocess.check_output(f"{pip} --version", shell=True, stderr=subprocess.DEVNULL)
            break
        except:
            pip = None
    if not pip:
        print("Must have Pip installed and on PATH. Download from: https://pip.pypa.io/en/stable/installation/.\nExiting...")
        exit()

    for p in packages:
        cmd = f"{pip} install {p} -q"
        try:
            subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL) # runs pip install <package> 
        except:
            print(f"Error installing {p} with {pip}:\n>>> ", end="")
            subprocess.run(cmd, shell=True) # will print error to terminal
            print("\nExiting...")
            exit()

    try:
        init_nonstd_modules()
    except ModuleNotFoundError:
        print("Error: Unable to install packages with Pip. Check internet connection.")
        exit()
    print("Complete.\n")

from program.utils import ensure_pandoc_installed
ensure_pandoc_installed() # ends termination if no pandoc

import sys
if len(sys.argv)==1:
    msg = "All installation requirements met."
    print("-"*len(msg))
    print(msg)
    print("-"*len(msg))
    print("Run `python3 main.py -h` for usage information.")
    print("Run `python3 main.py assets/example_input.md --learn` for example usage.\n")
    sys.exit()


# Begin normal excecution
import argparse
import os.path as path
import os

from program.utils import *

from program.input_parser import parse_input
from program.learn_exporter import export as learn
from program.moodle_exporter import export as moodle
from program.markdown_exporter import export as markdown
from program.markdown_exporter import mk_no_correct
from program.logger import Logger

from tabulate import tabulate

############
## PARSER ##
############
# gets user's input, validates all arguments, returns args
def get_user_args():
    ## MAKE PARSER ##
    parser = argparse.ArgumentParser(description=f'{get_logo()}\n\nDocumentation: https://github.com/lewisforbes/Quiz-Whiz/wiki',
                                    epilog="Note: at least one of --moodle, --learn and --file required.", formatter_class=argparse.RawDescriptionHelpFormatter)

    # required
    parser.add_argument('input', type=str,
                        help='path of input file/directory')

    # optional
    parser.add_argument('--output', '-o', type=str, dest='path',
                        help='path of output directory (default "output/")')

    # optional args to select output(s)
    outputs = parser.add_argument_group()
    outputs.add_argument('--moodle', '-m', action='store_true',
                        help='produce Moodle output')

    outputs.add_argument('--learn', '-l', action='store_true',
                        help='produce Learn output')

    outputs.add_argument('--file', '-f', type=str, dest="ext", nargs='+',
                        help='file extention(s) of output file(s)')

    # output modes
    parser.add_argument('--debug', '-d', action='store_true',
                        help='show detailed error messages')

    parser.add_argument('--no_colour', '-nc', action='store_true',
                        help="doesn't output colour to terminal")

    parser.add_argument('--quiet', '-q', action='store_true',
                        help='suppresses all non-error outputs')
    
    parser.add_argument('--basic', '-b', action='store_true',
                        help="outputs basic formatting")
    
    parser.add_argument('--log_to_file', '-ltf', action='store_true',
                        help=f"creates files {Logger.RECENT} and {Logger.RECENT} with headings.")

    # question numbers
    nums = parser.add_mutually_exclusive_group()
    nums.add_argument('--add_nums', '-an', action='store_true',
                        help='adds question numbers to input file(s)')

    nums.add_argument('--remove_nums', '-rn', action='store_true',
                        help='undos action of --add_nums')

    # parser.add_argument('--export', '-e', action='store_true', help="moves results to shared vm folder")

    args = parser.parse_args()

    if args.no_colour:
        Fore.BLACK           = ""
        Fore.RED             = ""
        Fore.GREEN           = ""
        Fore.YELLOW          = ""
        Fore.BLUE            = ""
        Fore.MAGENTA         = ""
        Fore.CYAN            = ""
        Fore.WHITE           = ""
        Fore.RESET           = ""

    if args.log_to_file:
        Logger() # create logger

    ## MANUAL ARGUMENT VALIDATION ##
    # ensure output format is specified
    if not (args.learn or args.moodle or args.ext):
        error('No output format specified. Include --moodle and/or --learn and/or --file')

    # output dirname validation
    if args.path and (os.path.abspath("program") in os.path.abspath(args.path)):
        error("Cannot write output within /program directory.")

    ## PROGRAM CONFIG ##
    Progress.basic = args.basic
    Progress.quiet = args.quiet

    return args

##########
## MAIN ##
##########
# split into subfunctions for readability. each is called once only.
def main(args):    
    # creat one Quiz per input file, display parse summary, return [Quiz]
    def parse(input_arg):
        # deals with --add_nums and --remove_nums
        def nums_flags(args, inputs):
            assert not (args.add_nums and args.remove_nums)
            # qnum = COMMENT + " Question {} //\n"
            qnum = COMMENT*2 + " Question {} " + COMMENT*2 + "\n" # no f"_" as using .format() later 
            if args.add_nums:
                for fpath in inputs:
                    q_i = 0
                    new_lines = []
                    f = safe_open(fpath, 'r')
                    qnum_present = False
                    for line in f:
                        if line[0]==Q_START:
                            q_i+=1
                            if not qnum_present:
                                new_lines.append(qnum.format(q_i))
                        new_lines.append(line)
                        qnum_present = line==qnum.format(q_i+1)

                    f.close()
                    f = safe_open(fpath, 'w')
                    f.writelines(new_lines)
                    f.close()
            if args.remove_nums:
                for fpath in inputs:
                    new_lines = []
                    f = safe_open(fpath, 'r')
                    for line in f:
                        if re.match(qnum.format("[0-9]+"), line):
                            continue
                        new_lines.append(line)
                    f.close()
                    f = safe_open(fpath, 'w')
                    f.writelines(new_lines)
                    f.close()

        # get fpath(s) to parse
        if path.isdir(input_arg):
            inputs = [path.join(input_arg,f) for f in os.listdir(input_arg) if ("." in f)]
        else:
            inputs = [input_arg]
        
        nums_flags(args, inputs)
    
        quizzes = []
        s = "" if len(inputs)==1 else "s"
        if Logger.logging: Logger(heading="Parsing")
        my_print(f"Parsing {len(inputs)} input file{s} provided...")
        for i in inputs:
            Progress.import_file = path.basename(i)
            Progress.import_fpath = i
            quizzes.append(parse_input(i))
        Progress.import_file = None

        # set all Quiz.input_file
        assert len(quizzes)==len(inputs)
        for i,q in enumerate(quizzes):
            q.input_file = path.basename(inputs[i])
        
        # display parse summary
        my_print(make_parse_table(quizzes), end="", log=False) # added to log within make_parse_table
        return quizzes

    # creates specified output files for each Quiz, returns message with warning summary
    def output(quizzes, args):
        if Logger.logging: Logger(heading="Creating and Exporting Output")
        # sort out output dir
        if args.path:
            output_dir = args.path
        else:
            output_dir = "output"

        if not path.isdir(output_dir):
            try:
                os.mkdir(output_dir)
            except:
                error(f"Unable to create directory '{output_dir}'")
        
        my_print() # terminal newline

        # export quizzes
        for i, quiz in enumerate(quizzes):
            my_print(f"\nExporting {quiz.input_file}...")
            bname = path.basename(quiz.input_file)
            if args.learn:
                outpath = path.join(output_dir, f"LEARN_{change_ftype(bname, 'txt')}")
                learn(quiz, outpath)
                my_print(f"Learn file created: '{outpath}'\n")
            if args.moodle:
                outpath = path.join(output_dir, f"MOODLE_{change_ftype(bname, 'xml')}")
                moodle(quiz, outpath)
                my_print(f"Moodle file created. '{outpath}'\n")
            if args.ext:
                mk_tmp_dir()
                tmp_correct = path.join(TMP_DIR(), "for_file_convert.md")
                markdown(quiz, tmp_correct) # make markdown file with answers
                tmp_no_correct = mk_no_correct(tmp_correct) # make markdown file without answers
                for ftype in args.ext:
                    try:
                        # with answers
                        pypandoc.convert_file(tmp_correct, ftype, format='md', extra_args=['--mathjax'],
                                            outputfile=path.join(output_dir, f"{ftype.upper()}_sols_{change_ftype(bname, ftype)}",))
                        # without answers
                        pypandoc.convert_file(tmp_no_correct, ftype, format='md', extra_args=['--mathjax'],
                                        outputfile=path.join(output_dir, f"{ftype.upper()}_no_sols_{change_ftype(bname, ftype)}",))
                        my_print(f"{ftype} files created.")
                    except RuntimeError as e:
                        e = str(e)                    
                        if "Invalid output format" in e: 
                            error(f"Invalid file type specified ({ftype}). Must be one of:\n{e.split(':')[1]}")
                        else:
                            error("Unexpected pandoc error occured.\n" + e.replace("\nTry pandoc --help for more information.", ""))
                del_tmp_dir()
            if len(quizzes)>1 and not Progress.basic and i!=len(quizzes)-1 :
                my_print("- "*30)

        # # TODO delete
        # if args.export:
        #     to_vm(output_dir)
        # # end delete
        
        # make "finished" message
        with_warnings = " with no warnings"
        if Progress.warn_count!=0:
            s= "" if Progress.warn_count==1 else "s"
            with_warnings = f" with {Progress.warn_count} warning{s}"
            if args.quiet:
                with_warnings+=". Rerun without --quiet (-q) for details"
        return f"{Fore.GREEN}Finished{with_warnings}.{Fore.RESET}"

    quizzes = parse(args.input)
    finished_msg = output(quizzes, args)
    
    if Logger.logging: Logger(heading="Final Message", content=finished_msg).export()
    print(finished_msg)

#################################
## MAIN EXCECUTION STARTS HERE ##
#################################
# for when the user presses CTRL Z or C
def user_end_ter():
    print(f"\n{Fore.RED}Ending termination.{Fore.RESET}")
    from time import sleep
    if Logger.logging: Logger(heading="Error Message", content="User killed termination.").export()
    exit()



args = get_user_args()

# this is here so it can be called after files are fixed in utils.
def go():
    ## NORMAL ## 
    if not args.debug:
        try:
            main(args)
        except SystemExit:
            pass # known error already displayed
        except KeyboardInterrupt:
            user_end_ter()
        except EOFError:
            user_end_ter()
        except:
            error("An unexpected error occured. Rerun with --debug flag for details.", show_progress=False)

    ## DEBUG ## 
    if args.debug:
        success = False
        try:
            main(args)
            success = True
        except SystemExit:
            success = True # known error occured
        except KeyboardInterrupt:
            user_end_ter()
            exit()
        except EOFError:
            user_end_ter()
            exit()
        except:
            # print Utils.Progress details
            if Progress.current_action=="":
                my_print(f"{Fore.YELLOW}No progress update since start of excecution or since Utils.Progress reset.{Fore.RESET}\n")
            else:
                my_print(f"{Fore.YELLOW}Error occured when{Progress.current_action}.{Fore.RESET}\n")
        if not success:
            Progress.quiet = True # don't reshow program output
            Logger.logging = False
            main(args) # show error in full

go()
## END OF FILE ##
