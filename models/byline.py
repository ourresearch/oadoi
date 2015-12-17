import re
from collections import defaultdict

from nameparser import HumanName
from validate_email import validate_email


class Byline:
    def __init__(self, raw_byline):
        self.raw_byline = raw_byline

    def _clean_byline(self):
        clean_byline = self.raw_byline
        if not clean_byline:
            return None

        # do these before the remove_pattern matching
        clean_byline = clean_byline.replace("<U+000a>", " ")
        clean_byline = clean_byline.replace("\n", " ")

        remove_patterns = [
            ur"\[.*?\]",            
            ur"\(.*?\)",   # here so can get before comma split
            ur"with.*$",
            ur"based on.*$",
            ur"assistance.*$",
            ur"derived from.*$",
            ur"uses.*$",
            ur"as represented by.*$",
            ur"contributions.*$",
            ur"under.*$",
            ur"and others.*$",
            ur"and many others.*$",
            ur"and authors.*$",
            ur"assisted.*$"
        ]
        for pattern in remove_patterns:
            clean_byline = re.sub(pattern, "", clean_byline, re.IGNORECASE | re.MULTILINE)

        halt_patterns = [" port", " adapted ", " comply "]
        for pattern in halt_patterns:
            if pattern in clean_byline.lower():
                print "has a halt pattern, so skipping this byline"
                return None

        clean_byline = clean_byline.replace(" & ", ",")
        clean_byline = clean_byline.replace(";", ",")
        clean_byline = re.sub(" and ", ",", clean_byline, re.IGNORECASE)
        self.clean_byline = clean_byline
        # print "clean byline", clean_byline
        return clean_byline  


    # should return unknown_author_response if no good pairs found
    def author_email_pairs(self):
        unknown_author_response = [{"name": "UNKNOWN", "email": None}]

        clean_byline = self._clean_byline()
        if not clean_byline:
            return unknown_author_response

        responses = []
        for author_clause in clean_byline.split(","):
            author_name = None
            author_email = None

            clause_replace_patterns = [
                "\(.*?\)",   # here so can get before comma split            
                "\[.*?\]",
                "\[.*?$"
                ]
            for pattern in clause_replace_patterns:
                author_clause = re.sub(pattern, "", author_clause, re.IGNORECASE)

            if not author_clause or (len(author_clause) < 6):
                pass

            if "<" in author_clause:
                (author_name, author_email) = author_clause.split("<", 1)
                author_email = re.sub("(>.*)", "", author_email)
                if not validate_email(author_email):
                    author_email = None
            else:
                author_name = author_clause

            if author_name:
                author_name = author_name.strip("\t .'(")
                author_name = author_name.strip('"')

            if author_name or author_email:
                responses.append({"name":author_name, "email":author_email})

        if not responses:
            responses = unknown_author_response

        return responses
        
