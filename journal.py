import os
import re
import codecs
from journals_lookup import journals_lookup

def create_journals_lookup_from_medline_dump():
    # get a medline dump like this:
    # from http://www.ncbi.nlm.nih.gov/nlmcatalog/?term=currentlyindexed%5BAll%5D
    # on April 2, 2015
    # Send To as Summary (text)    
    # put it in data/pubmed_journals.txt then run this

    current_dir = os.path.dirname(__file__)
    rel_path_to_unis_csv = "data/pubmed_journals.txt"
    absolute_path_to_unis_csv = os.path.join(current_dir, rel_path_to_unis_csv)

    with codecs.open(absolute_path_to_unis_csv, "r", "utf-8") as myfile:
        journals_str = myfile.read()
        journal_pattern = re.compile("\d+\. (.+?)\nISSN:", re.DOTALL)
        journals_list_rough = journal_pattern.findall(journals_str)

    journals_lookup = {}
    for orig_journal in journals_list_rough:
        clean_journal = orig_journal
        clean_journal = clean_journal.replace("\n", " ")
        clean_journal = clean_journal.replace("&amp", "&")
        clean_journal = clean_journal.replace("&;", "&")
        clean_journal = clean_journal.split("(")[0]
        clean_journal = clean_journal.split("/")[0]
        clean_journal = clean_journal.split("=")[0]
        clean_journal = clean_journal.split(" : ")[0]
        clean_journal = clean_journal.strip()
        journals_lookup[orig_journal] = clean_journal

    return journals_lookup


def replace_word(name, word):
    words = name.split(" ")
    with_replaced_words = words.replace(word, None)
    name_replaced = " ".join(with_replaced_words)
    return name_replaced



def is_journal_autocomplete_match(substring_name, full_name):
    substring_name = substring_name.lower()
    full_name = full_name.lower()

    # see http://stackoverflow.com/a/15658331/596939
    stop_words = ["the", "a", "an"]
    stop_words_regex = re.compile(r'\b%s\b' % r'\b|\b'.join(map(re.escape, stop_words)))
    substring_name = stop_words_regex.sub("", substring_name).strip()
    full_name = stop_words_regex.sub("", full_name).strip()

    # then remove duplicate spaces the above replacement might have caused
    # from http://stackoverflow.com/a/2077944/596939
    substring_name = " ".join(substring_name.split())
    full_name = " ".join(full_name.split())

    is_match = substring_name.startswith(full_name)
    return is_match



def filter_journal_list(name_starts_with, matches_max_num=8):
    display_journal_names = journals_lookup.values()
    results = [journal 
                for journal in display_journal_names 
                if is_journal_autocomplete_match(journal, name_starts_with)]
    return results[0:matches_max_num]



