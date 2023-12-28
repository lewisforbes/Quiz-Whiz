from markdown import markdown
import re
import base64
import pypandoc
import os
from shutil import rmtree

# (allows for future flexibility)
def error(msg):
    raise Exception(msg)

# returns True iff input is None, empty, or whitespace only
def is_blank(s):
    return s==None or s.strip()=="" 

# input: array
# output: array with null/blank/whitespace-only elements removed
def remove_blanks(arr):
    output = []
    for x in arr:
        if not is_blank(x):
            output.append(x)
    return output

# splits on the first blank (see utils.is_blank()) element in array. if no blank found, error.
# example input: ["a", "b", "", "c", "", "d"]
# example output: [["a", "b"], ["c", "", "d"]]
def split_on_blank(arr):
    fst = []
    snd = []
    blank_found = False
    for x in arr:
        if is_blank(x) and not blank_found:
            blank_found = True
            continue # do not add first blank to any output
        
        if blank_found:
            snd.append(x)
        else:
            fst.append(x)
    if not blank_found:
        error("no blank found in array provided")
    return [fst, snd]

# input: string
# output: Bool/int/string where appropriate
def force_type(s):
    # boolean
    if s.lower() == "true":    
        return True
    if s.lower() == "false":
        return False
    
    # int
    try:
        return int(s)
    except:
        pass

    # float
    try:
        return float(s)
    except:
        # string
        return s
    

# keeps everything afer after first space in line
def get_line_content(s):
    try:
        return s[s.index(" ")+1:]
    except:
        error("utils.get_line_contents with invalit input: " + str(s))

# str() for writing to files
def file_str(x):
    if x:
        return str(x)
    else:
        return "" # x==None
    
def md_to_html(md_str):
    # duplicate all newlines *not* within a code block
    def add_new_lines(md_str): # this function is wild (derogatory)
        new_lines = re.finditer("\n", md_str)
        to_dupe_is = []
        for nl in new_lines:
            dupe = True
            for c in re.finditer("```.*?```", md_str, re.DOTALL): # for some reason you have to do this every loop 
                if nl.start()>=c.start() and nl.start()<c.end(): # if newline is within code
                    dupe = False
                    break
            if dupe:
                to_dupe_is.append(nl.start())
            
        to_dupe_is.sort(reverse=True)
        for i in to_dupe_is:
            pre = md_str[0:i]
            post = md_str[i:]
            md_str = pre + "\n" + post

        return md_str

    def md_to_html_pandoc(md_str):
        add_new_lines(md_str)
        # write tmp_md file
        dname = "tmp_files_for_pandoc_convert" 
        if not os.path.exists(dname):
            os.mkdir(dname)
        md_fpath = dname+"/tmp.md"
        f = open(md_fpath, "w")
        f.write(md_str)
        f.close()

        # use pandoc to create tmp html file
        html_fpath = dname+"/tmp.html"
        pypandoc.convert_file(md_fpath, 'html', format='md', outputfile=html_fpath)


        # read html file contents
        f = open(html_fpath, "r", encoding="utf-8")
        html = f.read()
        f.close()

        # delete tmp directory
        rmtree(dname)

        return html[:-1] # pandoc adds trailing newline 

    def img_to_b64(fpath):
        with open(fpath, "rb") as f:
            data = str(base64.b64encode(f.read()))
            return "data:image/;base64, {}".format(data.replace("'", "")[1:])
        
    # # convert to HTML. pandoc deals with newlines weirdly.
    # html = ""
    # for line in md_str.split("\n"):
    #     html += md_to_html_pandoc(line)
    
    html = md_to_html_pandoc(md_str)
    html = html.replace("\n", " ") # learn automatically includes newlines beacuse of seperate <p> tags


    # deal with images
    srcs = re.findall("src=\".*?\"", html)
    for src in srcs:
        if len(re.findall("https*?://", src))==0:
            # images are local
            im_path = re.findall("\".*\"", src)[0].replace("\"", "")
            html = html.replace(src, "src=\"{}\"".format(img_to_b64(im_path)))
    html = re.sub("<figcaption.*?<\/figcaption>", " ", html) # remove figcaption tag

    return html


CLEANR = re.compile('<.*?>') 
def remove_tags(raw_html):
  cleantext = re.sub(CLEANR, '', raw_html)
  return cleantext