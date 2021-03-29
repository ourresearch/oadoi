import datetime
import time
import unicodedata
import sqlalchemy
import logging
import math
import bisect
import urlparse
import re
import os
import collections
import requests
import heroku3
import json
import copy
from bs4 import UnicodeDammit
from unidecode import unidecode
from lxml import etree
from lxml import html
from sqlalchemy import sql
from sqlalchemy import exc
from subprocess import call
from requests.adapters import HTTPAdapter

class NoDoiException(Exception):
    pass

class DelayedAdapter(HTTPAdapter):
    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        # logger.info(u"in DelayedAdapter getting {}, sleeping for 2 seconds".format(request.url))
        # sleep(2)
        start_time = time.time()
        response = super(DelayedAdapter, self).send(request, stream, timeout, verify, cert, proxies)
        # logger.info(u"   HTTPAdapter.send for {} took {} seconds".format(request.url, elapsed(start_time, 2)))
        return response


# from http://stackoverflow.com/a/3233356/596939
def update_recursive_sum(d, u):
    for k, v in u.iteritems():
        if isinstance(v, collections.Mapping):
            r = update_recursive_sum(d.get(k, {}), v)
            d[k] = r
        else:
            if k in d:
                d[k] += u[k]
            else:
                d[k] = u[k]
    return d

# returns dict with values that are proportion of all values
def as_proportion(my_dict):
    if not my_dict:
        return {}
    total = sum(my_dict.values())
    resp = {}
    for k, v in my_dict.iteritems():
        resp[k] = round(float(v)/total, 2)
    return resp

def calculate_percentile(refset, value):
    if value is None:  # distinguish between that and zero
        return None

    matching_index = bisect.bisect_left(refset, value)
    percentile = float(matching_index) / len(refset)
    # print u"percentile for {} is {}".format(value, percentile)

    return percentile

def clean_html(raw_html):
  cleanr = re.compile(u'<.*?>')
  cleantext = re.sub(cleanr, u'', raw_html)
  return cleantext

# good for deduping strings.  warning: output removes spaces so isn't readable.
def normalize(text):
    response = text.lower()
    response = unidecode(unicode(response))
    response = clean_html(response)  # has to be before remove_punctuation
    response = remove_punctuation(response)
    response = re.sub(ur"\b(a|an|the)\b", u"", response)
    response = re.sub(ur"\b(and)\b", u"", response)
    response = re.sub(u"\s+", u"", response)
    return response

def normalize_simple(text):
    response = text.lower()
    response = remove_punctuation(response)
    response = re.sub(ur"\b(a|an|the)\b", u"", response)
    response = re.sub(u"\s+", u"", response)
    return response

def remove_everything_but_alphas(input_string):
    # from http://stackoverflow.com/questions/265960/best-way-to-strip-punctuation-from-a-string-in-python
    only_alphas = input_string
    if input_string:
        only_alphas = u"".join(e for e in input_string if (e.isalpha()))
    return only_alphas

def remove_punctuation(input_string):
    # from http://stackoverflow.com/questions/265960/best-way-to-strip-punctuation-from-a-string-in-python
    no_punc = input_string
    if input_string:
        no_punc = u"".join(e for e in input_string if (e.isalnum() or e.isspace()))
    return no_punc

# from http://stackoverflow.com/a/11066579/596939
def replace_punctuation(text, sub):
    punctutation_cats = set(['Pc', 'Pd', 'Ps', 'Pe', 'Pi', 'Pf', 'Po'])
    chars = []
    for my_char in text:
        if unicodedata.category(my_char) in punctutation_cats:
            chars.append(sub)
        else:
            chars.append(my_char)
    return u"".join(chars)


# from http://stackoverflow.com/a/22238613/596939
def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError ("Type not serializable")

def conversational_number(number):
    words = {
        "1.0": "one",
        "2.0": "two",
        "3.0": "three",
        "4.0": "four",
        "5.0": "five",
        "6.0": "six",
        "7.0": "seven",
        "8.0": "eight",
        "9.0": "nine",
    }

    if number < 1:
        return round(number, 2)

    elif number < 1000:
        return int(math.floor(number))

    elif number < 1000000:
        divided = number / 1000.0
        unit = "thousand"

    else:
        divided = number / 1000000.0
        unit = "million"

    short_number = '{}'.format(round(divided, 2))[:-1]
    if short_number in words:
        short_number = words[short_number]

    return short_number + " " + unit



def safe_commit(db):
    try:
        db.session.commit()
        return True
    except (KeyboardInterrupt, SystemExit):
        # let these ones through, don't save anything to db
        raise
    except sqlalchemy.exc.DataError:
        db.session.rollback()
        print u"sqlalchemy.exc.DataError on commit.  rolling back."
    except Exception:
        db.session.rollback()
        print u"generic exception in commit.  rolling back."
        logging.exception("commit error")
    return False


def is_pmc(url):
    return any(f in url for f in [u"ncbi.nlm.nih.gov/pmc", u"europepmc.org/articles/", u"europepmc.org/pmc/articles/"])


def is_doi_url(url):
    if not url:
        return False

    # test urls at https://regex101.com/r/yX5cK0/2
    p = re.compile("https?:\/\/(?:dx.)?doi.org\/(.*)")
    matches = re.findall(p, url.lower())
    if len(matches) > 0:
        return True
    return False


def normalize_doi(doi, return_none_if_error=False):
    if not doi:
        if return_none_if_error:
            return None
        else:
            raise NoDoiException("There's no DOI at all.")

    doi = doi.strip().lower()

    # test cases for this regex are at https://regex101.com/r/zS4hA0/4
    p = re.compile(ur'(10\.\d+/[^\s]+)')
    matches = re.findall(p, doi)

    if len(matches) == 0:
        if return_none_if_error:
            return None
        else:
            raise NoDoiException("There's no valid DOI.")

    doi = matches[0]

    # clean_doi has error handling for non-utf-8
    # but it's preceded by a call to remove_nonprinting_characters
    # which calls to_unicode_or_bust with no error handling
    # clean/normalize_doi takes a unicode object or utf-8 basestring or dies
    doi = to_unicode_or_bust(doi)

    return doi


def clean_doi(dirty_doi, return_none_if_error=False):
    if not dirty_doi:
        if return_none_if_error:
            return None
        else:
            raise NoDoiException("There's no DOI at all.")

    dirty_doi = normalize_doi(dirty_doi, return_none_if_error=return_none_if_error)

    if not dirty_doi:
        if return_none_if_error:
            return None
        else:
            raise NoDoiException("There's no valid DOI.")

    dirty_doi = remove_nonprinting_characters(dirty_doi)

    try:
        resp = unicode(dirty_doi, "utf-8")  # unicode is valid in dois
    except (TypeError, UnicodeDecodeError):
        resp = dirty_doi

    # remove any url fragments
    if u"#" in resp:
        resp = resp.split(u"#")[0]

    # remove double quotes, they shouldn't be there as per http://www.doi.org/syntax.html
    resp = resp.replace('"', '')

    # remove trailing period, comma -- it is likely from a sentence or citation
    if resp.endswith(u",") or resp.endswith(u"."):
        resp = resp[:-1]

    return resp


def pick_best_url(urls):
    if not urls:
        return None

    #get a backup
    response = urls[0]

    # now go through and pick the best one
    for url in urls:
        # doi if available
        if "doi.org" in url:
            response = url

        # anything else if what we currently have is bogus
        if response == "http://www.ncbi.nlm.nih.gov/pmc/articles/PMC":
            response = url

    return response

def date_as_iso_utc(datetime_object):
    if datetime_object is None:
        return None

    date_string = u"{}{}".format(datetime_object, "+00:00")
    return date_string


def dict_from_dir(obj, keys_to_ignore=None, keys_to_show="all"):

    if keys_to_ignore is None:
        keys_to_ignore = []
    elif isinstance(keys_to_ignore, basestring):
        keys_to_ignore = [keys_to_ignore]

    ret = {}

    if keys_to_show != "all":
        for key in keys_to_show:
            ret[key] = getattr(obj, key)

        return ret


    for k in dir(obj):
        value = getattr(obj, k)

        if k.startswith("_"):
            pass
        elif k in keys_to_ignore:
            pass
        # hide sqlalchemy stuff
        elif k in ["query", "query_class", "metadata"]:
            pass
        elif callable(value):
            pass
        else:
            try:
                # convert datetime objects...generally this will fail becase
                # most things aren't datetime object.
                ret[k] = time.mktime(value.timetuple())
            except AttributeError:
                ret[k] = value
    return ret


def median(my_list):
    """
    Find the median of a list of ints

    from https://stackoverflow.com/questions/24101524/finding-median-of-list-in-python/24101655#comment37177662_24101655
    """
    my_list = sorted(my_list)
    if len(my_list) < 1:
            return None
    if len(my_list) %2 == 1:
            return my_list[((len(my_list)+1)/2)-1]
    if len(my_list) %2 == 0:
            return float(sum(my_list[(len(my_list)/2)-1:(len(my_list)/2)+1]))/2.0


def underscore_to_camelcase(value):
    words = value.split("_")
    capitalized_words = []
    for word in words:
        capitalized_words.append(word.capitalize())

    return "".join(capitalized_words)

def chunks(l, n):
    """
    Yield successive n-sized chunks from l.

    from http://stackoverflow.com/a/312464
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

def page_query(q, page_size=1000):
    offset = 0
    while True:
        r = False
        print "util.page_query() retrieved {} things".format(page_query())
        for elem in q.limit(page_size).offset(offset):
            r = True
            yield elem
        offset += page_size
        if not r:
            break

def elapsed(since, round_places=2):
    return round(time.time() - since, round_places)



def truncate(str, max=100):
    if len(str) > max:
        return str[0:max] + u"..."
    else:
        return str


def str_to_bool(x):
    if x.lower() in ["true", "1", "yes"]:
        return True
    elif x.lower() in ["false", "0", "no"]:
        return False
    else:
        raise ValueError("This string can't be cast to a boolean.")

# from http://stackoverflow.com/a/20007730/226013
ordinal = lambda n: "%d%s" % (n,"tsnrhtdd"[(n/10%10!=1)*(n%10<4)*n%10::4])

#from http://farmdev.com/talks/unicode/
def to_unicode_or_bust(obj, encoding='utf-8'):
    if isinstance(obj, basestring):
        if not isinstance(obj, unicode):
            obj = unicode(obj, encoding)
    return obj

def remove_nonprinting_characters(input, encoding='utf-8'):
    input_was_unicode = True
    if isinstance(input, basestring):
        if not isinstance(input, unicode):
            input_was_unicode = False

    unicode_input = to_unicode_or_bust(input)

    # see http://www.fileformat.info/info/unicode/category/index.htm
    char_classes_to_remove = ["C", "M", "Z"]

    response = u''.join(c for c in unicode_input if unicodedata.category(c)[0] not in char_classes_to_remove)

    if not input_was_unicode:
        response = response.encode(encoding)

    return response

# getting a "decoding Unicode is not supported" error in this function?
# might need to reinstall libaries as per
# http://stackoverflow.com/questions/17092849/flask-login-typeerror-decoding-unicode-is-not-supported
class HTTPMethodOverrideMiddleware(object):
    allowed_methods = frozenset([
        'GET',
        'HEAD',
        'POST',
        'DELETE',
        'PUT',
        'PATCH',
        'OPTIONS'
    ])
    bodyless_methods = frozenset(['GET', 'HEAD', 'OPTIONS', 'DELETE'])

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        method = environ.get('HTTP_X_HTTP_METHOD_OVERRIDE', '').upper()
        if method in self.allowed_methods:
            method = method.encode('ascii', 'replace')
            environ['REQUEST_METHOD'] = method
        if method in self.bodyless_methods:
            environ['CONTENT_LENGTH'] = '0'
        return self.app(environ, start_response)


# could also make the random request have other filters
# see docs here: https://github.com/CrossRef/rest-api-doc/blob/master/rest_api.md#sample
# usage:
# dois = get_random_dois(50000, from_date="2002-01-01", only_journal_articles=True)
# dois = get_random_dois(100000, only_journal_articles=True)
# fh = open("data/random_dois_articles_100k.txt", "w")
# fh.writelines(u"\n".join(dois))
# fh.close()
def get_random_dois(n, from_date=None, only_journal_articles=True):
    dois = []
    while len(dois) < n:
        # api takes a max of 100
        number_this_round = min(n, 100)
        url = u"https://api.crossref.org/works?sample={}".format(number_this_round)
        if only_journal_articles:
            url += u"&filter=type:journal-article"
        if from_date:
            url += u",from-pub-date:{}".format(from_date)
        print url
        print "calling crossref, asking for {} dois, so far have {} of {} dois".format(
            number_this_round, len(dois), n)
        r = requests.get(url)
        items = r.json()["message"]["items"]
        dois += [item["DOI"].lower() for item in items]
    return dois


# from https://github.com/elastic/elasticsearch-py/issues/374
# to work around unicode problem
# class JSONSerializerPython2(elasticsearch.serializer.JSONSerializer):
#     """Override elasticsearch library serializer to ensure it encodes utf characters during json dump.
#     See original at: https://github.com/elastic/elasticsearch-py/blob/master/elasticsearch/serializer.py#L42
#     A description of how ensure_ascii encodes unicode characters to ensure they can be sent across the wire
#     as ascii can be found here: https://docs.python.org/2/library/json.html#basic-usage
#     """
#     def dumps(self, data):
#         # don't serialize strings
#         if isinstance(data, elasticsearch.compat.string_types):
#             return data
#         try:
#             return json.dumps(data, default=self.default, ensure_ascii=True)
#         except (ValueError, TypeError) as e:
#             raise elasticsearch.exceptions.SerializationError(data, e)



def get_tree(page):
    page = page.replace("&nbsp;", " ")  # otherwise starts-with for lxml doesn't work
    try:
        encoding = UnicodeDammit(page, is_html=True).original_encoding
        parser = html.HTMLParser(encoding=encoding)
        tree = html.fromstring(page, parser=parser)
    except (etree.XMLSyntaxError, etree.ParserError) as e:
        print u"not parsing, beause etree error in get_tree: {}".format(e)
        tree = None
    return tree


def is_the_same_url(url1, url2):
    norm_url1 = strip_jsessionid_from_url(url1.replace("https", "http"))
    norm_url2 = strip_jsessionid_from_url(url2.replace("https", "http"))
    if norm_url1 == norm_url2:
        return True
    return False

def strip_jsessionid_from_url(url):
    url = re.sub(ur";jsessionid=\w+", "", url)
    return url

def get_link_target(url, base_url, strip_jsessionid=True):
    if strip_jsessionid:
        url = strip_jsessionid_from_url(url)
    if base_url:
        url = urlparse.urljoin(base_url, url)
    return url


def fix_url_scheme(url):
    if url and urlparse.urlparse(url).hostname in [
        u'revista-iberoamericana.pitt.edu',
        u'www.spandidos-publications.com',
    ]:
        url = re.sub(ur'^http://', u'https://', url)

    return url

def run_sql(db, q):
    q = q.strip()
    if not q:
        return
    start = time.time()
    try:
        con = db.engine.connect()
        trans = con.begin()
        con.execute(q)
        trans.commit()
    except exc.ProgrammingError as e:
        pass
    finally:
        con.close()

def get_sql_answer(db, q):
    row = db.engine.execute(sql.text(q)).first()
    return row[0]

def get_sql_answers(db, q):
    rows = db.engine.execute(sql.text(q)).fetchall()
    if not rows:
        return []
    return [row[0] for row in rows]

def normalize_title(title):
    if not title:
        return ""

    # just first n characters
    response = title[0:500]

    # lowercase
    response = response.lower()

    # deal with unicode
    response = unidecode(unicode(response))

    # has to be before remove_punctuation
    # the kind in titles are simple <i> etc, so this is simple
    response = clean_html(response)

    # remove articles and common prepositions
    response = re.sub(ur"\b(the|a|an|of|to|in|for|on|by|with|at|from)\b", u"", response)

    # remove everything except alphas
    response = remove_everything_but_alphas(response)

    return response


# from https://gist.github.com/douglasmiranda/5127251
# deletes a key from nested dict
def delete_key_from_dict(dictionary, key):
    for k, v in dictionary.iteritems():
        if k == key:
            yield v
        elif isinstance(v, dict):
            for result in delete_key_from_dict(key, v):
                yield result
        elif isinstance(v, list):
            for d in v:
                for result in delete_key_from_dict(key, d):
                    yield result


def restart_dynos(app_name, dyno_prefix):
    heroku_conn = heroku3.from_key(os.getenv('HEROKU_API_KEY'))
    app = heroku_conn.apps()[app_name]
    dynos = app.dynos()
    for dyno in dynos:
        if dyno.name.startswith(dyno_prefix):
            dyno.restart()
            print u"restarted {} on {}!".format(dyno.name, app_name)


def is_same_publisher(publisher1, publisher2):
    if publisher1 and publisher2:
        return normalize(publisher1) == normalize(publisher2)
    return False


def clamp(val, low, high):
    return max(low, min(high, val))


def normalize_issn(issn):
    return issn.replace(u'-', '').lower()


def is_same_issn(l, r):
    return normalize_issn(l) == normalize_issn(r)
