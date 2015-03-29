

def make_key(*args):
    return "ti:" + ":".join(args)

def make_refset_key(pmid):
    return make_key("article", pmid, "refset")