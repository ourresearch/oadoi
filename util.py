import time
from app import db






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




