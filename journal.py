import os
import re
import codecs
from journals_list import journals_list

def create_journals_list_from_medline_dump():
    # get a medline dump like this:
    # from http://www.ncbi.nlm.nih.gov/nlmcatalog/?term=currentlyindexed%5BAll%5D
    # on April 2, 2015
    # Send To as Summary (text)    
    # put it in data/pubmed_journals.txt then run this

    global journals_list

    journals_list = journals_list

    current_dir = os.path.dirname(__file__)
    rel_path_to_unis_csv = "data/pubmed_journals.txt"
    absolute_path_to_unis_csv = os.path.join(current_dir, rel_path_to_unis_csv)

    with codecs.open(absolute_path_to_unis_csv, "r", "utf-8") as myfile:
        journals_str = myfile.read()
        journal_pattern = re.compile("\d+\. (.+?)\nISSN:", re.DOTALL)
        journals_list = journal_pattern.findall(journals_str)

    journals_list = [j.lower() for j in journals_list]



def filter_journal_list(name_starts_with, max_len=8):
    lower_name = name_starts_with.lower()
    results = [journal for journal in journals_list if journal.startswith(lower_name)]
    return results[0:max_len]


