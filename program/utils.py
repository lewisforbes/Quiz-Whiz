# Utils used accross program
from markdown import markdown # TODO remove. talk about in report.
import re
import base64
import pypandoc
import os
from shutil import rmtree, copy
import sys
from colorama import Fore, init
init()

#############
## STRINGS ##
#############

# input: string
# output: True iff input is None/blank/whitespace-only
def is_blank(s, space_is_blank=True):
    if not space_is_blank:
        s = s.replace(" ", "-") # - not removed by strip
    return s==None or s.strip()==""

# removes HTML tags 
def remove_tags(raw_html):
  return re.sub("<.*?>", "", raw_html)

# removes first 'word' from string  
# generally removes - / x. / #
# input_parser.verify_answers() should ensure assertions
def get_line_content(s):
    assert (" " in s)
    content = s.split(" ")
    assert re.match("[0-9]+\.", content[0]) or content[0] in ["-", "#"]
    output = ""
    for x in content[1:]:
        output += x + " "
    output = output[:-1] # remove extra space at the end
    return output

# input: string
# output: output ready to be written to file
def file_str(x):
    if x:
        return str(x)
    else:
        return ""
    
# input: string
# output: Bool/int/string where appropriate
def force_type(s):
    if s.lower() == "true":    
        return True
    if s.lower() == "false":
        return False

    try:
        return int(s)
    except:
        pass

    try:
        return float(s)
    except:
        return s # returns string
    
# converts a markdown string to an HTML string
def md_to_html(md_str):
    # input: raw markdown
    # output: markdown with newlines outside of code blocks duplicated 
    def format_not_code(md_str):
        code_is = [(m.start(), m.end()) for m in re.finditer("```(.|\n)*?```", md_str)]
        nl_to_dupe = []
        for nl_i in [m.start() for m in re.finditer("\n", md_str)]:
            dupe = True
            for code_i in code_is:
                if nl_i>=code_i[0] and nl_i<code_i[1]: # if nl_i within code block
                    dupe = False
                    break
            # nl_i is not within code block
            if dupe:
                nl_to_dupe.append(nl_i)
        for nl_i in sorted(nl_to_dupe, reverse=True):
            md_str = sub_range(md_str, "\n\n", nl_i, nl_i+1)
        return md_str

    # input: markdown string
    # output: raw pandoc conversion to html of input
    def md_to_html_pandoc(md_str):
        # (over)write tmp_md file
        mk_tmp_dir() 
        md_fpath = TMP_DIR()+"/md_tmp.md"
        f = open(md_fpath, "w")
        f.write(md_str)
        f.close()

        # use pandoc to create tmp html file
        html_fpath = TMP_DIR()+"/html_tmp.html"
        pypandoc.convert_file(md_fpath, 'html', format='md', outputfile=html_fpath)

        # read html file contents
        f = open(html_fpath, "r", encoding="utf-8")
        html = f.read()
        f.close()

        return html
    
    # input: html generated by pandoc
    # output: html with <br> instead of \n in code blocks
    def format_code(html):
        # code for which user has specified language
        PATTERN = '<div class="sourceCode"(.|\n)*?<\/div>'
        match = re.search(PATTERN, html)
        while match and ("\n" in match.group(0)):
            match_str = re.sub("<\/span>\n<span", "</span><br><span", match.group(0)) # add code newlines
            match_str = re.sub("<pre\n", "<pre ", match_str) # remove newline in pre tag

            html = sub_range(html, match_str, match.start(), match.end())
            match = re.search(PATTERN, html)
        
        # code for which user has not specified language
        PATTERN = "<pre><code>(.|\n)*?<\/code><\/pre>"
        match = re.search(PATTERN, html)
        while match and ("\n" in match.group(0)):
            match_str = re.sub("\n", "<br>", match.group(0))
            html = sub_range(html, match_str, match.start(), match.end())
            match = re.search(PATTERN, html)
        
        return html
        
    # input: html with images converted by pandoc
    # output: html with images adjusted for import
    def format_images(html):
        # input: filepath of local image
        # output: string of image encoded in base64
        def img_to_b64(fpath):
            with safe_open(fpath, "rb") as f:
                data = str(base64.b64encode(f.read()))
                return "data:image/;base64, {}".format(data.replace("'", "")[1:])

        srcs = re.findall("src=\".*?\"", html)
        for src in srcs:
            if len(re.findall("https*?://", src))==0:
                # images are local
                im_path = re.findall("\".*\"", src)[0].replace("\"", "")
                html = html.replace(src, "src=\"{}\"".format(img_to_b64(im_path)))
        # fix alt text
        alts = re.findall("<figcaption>(.*?)<\/figcaption>", html)
        for alt in alts: # skipped if no alt text
            old_re = 'alt="".*?\/><figcaption>{}<\/figcaption>'.format(alt)
            assert re.search(old_re, html) # ensure structure is as expected
            html = re.sub(old_re, 'alt="{}"/> '.format(alt), html) # move alt text to alt="", remove figcaption tag
        return html


    ## CHOOSE HOW TO CONVERT INITIAL MD ##
    if ("*" in md_str) or ("_" in md_str) or ("[" in md_str) or ("`" in md_str):
        md_str = format_not_code(md_str)
        html = md_to_html_pandoc(md_str)
    else:
        html = f"<p>{md_str}</p>".replace("\n", "</p> <p>")
    
    ## FIX FORMATTING ETC FOR IMPORTING ## 
    html = format_code(html)
    html = html.replace("\n", " ") # all remaining newlines redundant
    html = re.sub("<p> *?<\/p>", "<br>", html) # replace blank <p> tags with <br>
    html = format_images(html)
    return html

# replaces provided range in old_str with sub
def sub_range(old_str, sub_str, start, end):
    if end<start or start<0 or end>len(old_str):
        error("utils.sub_range() not being used as intended.") 
    start_str = old_str[0:start]
    end_str = old_str[end:]
    return start_str + sub_str + end_str

# returns the properties from a raw question/answer string
# format: << name1:val1; name2:val2 >>
def get_props(s):
    props_pattern = "<<((?:\n|.)*?)>>"
    props = re.findall(props_pattern, s)
    if len(props)==0 or props[0].strip()=="":
        return None
    
    props = props[-1].replace("\n", "")
    props_arr = remove_blanks(props.split(";"))
    output = {}
    for p in props_arr:
        n_v = [s.strip() for s in p.split(":")]
        if len(n_v)!=2:
            error(f"Property '{p}' is invalid.")
        output[n_v[0]]=n_v[1]
    return output

# removes properties from a string
def remove_props(s):
    if s==None:
        return None
    props_pattern = "<<((?:\n|.)*?)>>"
    return re.sub(props_pattern, "", s)

############
## ARRAYS ##
############

# arr: array
# space_is_blank: True iff space(s) considered blank
# output: array with blank elements removed
def remove_blanks(arr):
    output = []
    for x in arr:
        if not is_blank(x):
            output.append(x)
    return output

# input: array
# output: [array, array]
# explaination: splits on the first blank element in arr. if no blank found, returns None
def split_on_blank(arr, space_is_blank=True):
    fst = []
    snd = []
    blank_found = False
    for x in arr:
        if is_blank(x, space_is_blank) and not blank_found:
            blank_found = True
            continue # do not add first blank to any output
        
        if blank_found:
            snd.append(x)
        else:
            fst.append(x)
    return [fst, snd]

# returns the intersection of two arrays
def get_intersection(arr1, arr2):
    output = []
    for e1 in arr1:
        for e2 in arr2:
            if e1==e2:
                output.append(e1)
    return output


############
## ERRORS ##
############

# prints error and terminates program
# progress always shown apart from when error is unexpected.
def error(msg, show_progress=True):
    newline = "\n> "
    progress = Progress.current_action
    if not show_progress or progress=="":
        newline = ""
    else:
        msg = msg.replace("\n", newline)
    
    print(f"{Fore.RED}Error{progress}: {newline}{msg}{Fore.RESET}")
    del_tmp_dir()
    sys.exit()

# keeps track of progress for more descriptive errors
class Progress:
    current_q = 0
    current_action = "" # parsing, exporting to moodle, exporting to learn

    def parse_update():
        Progress.current_q+=1
        Progress.current_action = f" parsing question {Progress.current_q}"

    def export_update(service):
        Progress.current_q+=1
        Progress.current_action = f" exporting question {Progress.current_q} to {service}"

    def reset():
        Progress.current_q = 0
        Progress.current_action = ""

# prints warning message but doesn't exit program
def warning(msg, show_progress=True):
    progress = Progress.current_action
    if not show_progress:
        progress = ""
    print(f"{Fore.BLUE}Warning while{progress}: {msg}{Fore.RESET}")

###########
## FILES ##
###########
def TMP_DIR():
    return "program/temporary_directory_which_will_be_deleted!!!!!!!!/"

# creates directory TMP_DIR() if it doesn't exist
def mk_tmp_dir():
    if not os.path.exists(TMP_DIR()):
        os.mkdir(TMP_DIR())

def del_tmp_dir():
    if os.path.exists(TMP_DIR()):
        rmtree(TMP_DIR())

# defaults copy all output files to vm shared dir
def file_copy(clear_output=False, current=None, new="/afs/inf.ed.ac.uk/user/s18/s1843023/Documents/new_vm/shared"):
    if clear_output:
        assert new=="/afs/inf.ed.ac.uk/user/s18/s1843023/Documents/new_vm/shared"
        for f in os.listdir(new):
            try:
                os.remove(new+"/"+f)
            except:
                pass

    if current==None:
        to_copy = ["output/"+str(f) for f in os.listdir("output/") if ("." in f)]
    else:
        to_copy=[current]

    for fpath in to_copy:
        copy(fpath, new)

# open() with error checking
def safe_open(fpath, m, encoding=None):
    if m=="r" and not os.path.exists(fpath):
        error("Provided input file path does not exist.")
    try:
        if encoding:
            return open(fpath, m, encoding=encoding)
        else:
            return open(fpath, m)
    except:
        error(f"Could not open/write file '{fpath}'")

# change file type of filepath
def change_ftype(fpath, newtype):
    return os.path.splitext(fpath)[0]+"."+newtype.replace(".", "")

# returns the comment marker
def comment():
    return "//"