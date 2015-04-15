from collections import defaultdict
from util import dict_from_dir
from util import median


def make_journals_dict(articles):
    journals_dict = defaultdict(list)
    for article in articles:
        journal_name = article["biblio"]["journal"]
        journals_dict[journal_name].append(article)
    return journals_dict

def make_journals_histogram(articles, num_bins=100):
    journals_dict = make_journals_dict(articles)
    hist = JournalsHistogram(journals_dict, num_bins)
    return hist


class JournalsHistogram(object):

    def __init__(self, journals_dict, num_bins):
        self.journals = []
        for journal_name, journal_articles in journals_dict.iteritems():
            my_refset_journal_obj = RefsetJournal(
                journal_name,
                journal_articles,
                num_bins
            )
            self.journals.append(my_refset_journal_obj)


    def to_dict(self):
        return {
            "max_bin_size": max([j.get_max_bin_size() for j in self.journals]),
            "list": [j.to_dict() for j in self.journals]
        }







""" Refset Journal stuff """


def make_histogram(articles, num_bins):
    ret = []
    for i in range(0, num_bins):
        my_bin = HistogramBin(i, articles)
        ret.append(my_bin)
    return ret



class RefsetJournal(object):
    def __init__(self, name, articles, num_bins):
        self.name = name
        self.articles = articles
        self.histogram = make_histogram(articles, num_bins)

    def get_max_bin_size(self):
        return max(len(b.articles) for b in self.histogram)

    def to_dict(self):
        return {
            "name": self.name,
            "num_articles": len(self.articles),
            "articles": self.articles,
            "scopus_bins": [b.to_dict() for b in self.histogram],
            "scopus_median": median([a["scopus"] for a in self.articles])
        }






""" Histogrom Bin stuff """


def filter_articles_by_scopus(scopus_count, articles):
    ret = []
    for article in articles:
        try:
            if int(article["scopus"]) == scopus_count:
                ret.append(article)
        except (ValueError, TypeError):  # scopus is a string or None
            pass
    return ret


class HistogramBin(object):
    def __init__(self, scopus_count, potential_articles):
        self.scopus_count = int(scopus_count)
        self.articles = filter_articles_by_scopus(self.scopus_count, potential_articles)

    def to_dict(self):
        return dict_from_dir(self)





