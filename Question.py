from enum import Enum
from utils import *
from abc import ABC, abstractmethod
from Answer import Answer
import re

# Question Types #
class QType(Enum):
    MC = 1     # Basic()
    TF = 2     # Basic()
    ESSAY = 3  # Basic()
    CLOZE = 4  # Cloze()
    MATCH = 5  # Match()
    NUM = 6    # Num()

#######################
# ABSTRACT SUPERCLASS #
#######################
class Question(ABC):
    def __str__(self):
        t = self.type
        if t:
            t = str(t).split(".")[1]
        s = "Question type: {}".format(t)
        s += "\nQ: {}\nD: {}".format(self.question, self.description)

        if self.answers:
            a_len = len(self.answers)
        else:
            a_len = None

        a_term = "answers"
        if self.type == QType.CLOZE:
            a_term = "blanks"
        elif self.type == QType.MATCH:
            a_term = "pairs"
        return s + "\nNumber of {}: {}\n".format(a_term, a_len)

    def __init__(self, question=None, description=None, answers=None, type=None):
        self.question    = question
        self.description = description
        self.answers     = answers
        self.type        = type

    def set_question(self, s):
        self.question = s
        return self
    
    def set_description(self, s):
        self.description = s
        return self
    
    def set_answers(self, a):
        self.answers = a
        return self

    def set_type(self, t):
        self.type = t
        return self

    # parses answers
    @abstractmethod
    def parse_answers(lines):
        pass


#######################
# CONCRETE SUBCLASSES #
#######################
class Basic(Question):
    CORRECT = "^"
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if "type" in kwargs.keys():
            error("type passed into Question.Basic")

        if "answers" in kwargs.keys():
            self.type = self.get_type()
            self.fix_answers()
        
    # overriding to determing QType etc
    def set_answers(self, answers):
        super().set_answers(answers)
        self.type = self.get_type()
        self.fix_answers()

    # once QType is decided, fix self.answers
    def fix_answers(self):
        assert self.type in [QType.TF, QType.MC, QType.ESSAY]

        if self.type == QType.TF:
            assert len(self.answers)==1
            self.answers[0].correct = True # mark current (only) answer as correct
            self.answers.append(Answer(not self.answers[0].body, False, None)) # add other Boolean to self.answers, mark it incorrect # TODO properties
            return

        if self.type == QType.MC:
            for a in self.answers:
                a.body = str(a.body) # convert all answers to string
            return                               


    def get_type(self):
        # check if type is ESSAY
        if not self.answers:
            return QType.ESSAY
        
        bodies = [a.body for a in self.answers]
        # check if type is TF
        if (bodies==[True] or bodies==[False]):
            return QType.TF

        return QType.MC

    # TODO is this used
    def get_correct_as(self):
        return [a for a in self.answers if a.correct]

    # static method
    # returns general [Answer], MC, TF etc not decided here 
    def parse_answers(lines):
        def parse_answer(raw_answer):
            raw_answer = get_line_content(raw_answer)

            props_pattern = "<<(.*?)>>"
            props = re.findall(props_pattern, raw_answer)
            if len(props)==0:
                props = None
            else:
                props = remove_blanks(props[-1].split(" "))

            raw_answer = re.sub(props_pattern, "", raw_answer).strip() # answer without bullet or properties
            if raw_answer[0]==Basic.CORRECT:
                correct = True
                body = raw_answer[len(Basic.CORRECT):] # removes correct marker 
            else:
                correct = False
                body = raw_answer

            return Answer(force_type(body), correct, props)

        if len(lines)==0:
            return None
        
        return [parse_answer(l) for l in lines]

class Cloze(Question):
    BLANK_MARKER = "[]"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.type   = QType.CLOZE
        if "question" in kwargs.keys():
            self.question = re.sub("\[.*?\]", Cloze.BLANK_MARKER, self.question) # standardises all blanks

    def verify(self):
        if not self.answers or not self.question:
            error("Cloze.verify() called before Close.answers and/or Cloze.question set") 

        if len(self.answers) != self.question.count(Cloze.BLANK_MARKER):
            print(self.question)
            error("Cloze poorly formatted")

    # static method
    def parse_answers(lines):
        return [(get_line_content(l)) for l in lines]
    
class Match(Question):
    SPLITTER = "///"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.type = QType.MATCH

    # static method
    def parse_answers(lines):
        lines = [get_line_content(l) for l in lines]
        
        pairs = []
        for l in lines:
            current = l.split(Match.SPLITTER)
            if len(current)!=2:
                error("match answers poorly formatted")
            pairs.append(current)
        
        return pairs

class Num(Question):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.type = QType.NUM

    # self.answers is of form ["x [y]"]. returns int y
    def get_tolerance(self):
        if not self.answers:
            return None
        try:
            return force_type(re.findall("\[[0-9]+\]", self.answers[0])[0][1:-1])
        except:
            error("Num answers poorly formatted")

    # self.answers is of form ["x [y]"]. returns int x
    def get_answer(self):
        if not self.answers:
            return None
        try:
            return force_type(self.answers[0].split(" ")[0])
        except:
            error("Num answers poorly formatted")

    # static method
    def parse_answers(lines):
        if not Num.is_num(lines):
            error("Num answers poorly formatted")

        return [get_line_content(lines[0])] # len(lines)=1
    
    # static method
    def is_num(ans_lines):
        if len(ans_lines)!=1:
            return False
        
        return re.match("[0-9]+ \[[0-9]+\]", get_line_content(ans_lines[0])) # ans line of form "x [y]" or "- x [y]"
