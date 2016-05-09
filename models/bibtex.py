from StringIO import StringIO
import json, re

from pybtex.database.input import bibtex
from pybtex.errors import enable_strict_mode, format_error
from pybtex.scanner import PybtexSyntaxError, PybtexError

from util import to_unicode_or_bust
from bibtex_char_lookup import bibtex_to_unicode


def _to_unicode(text):
    text = to_unicode_or_bust(text)
    if "{" in text:
        text = text.replace("\\", "")
        for i, j in bibtex_to_unicode.iteritems():
            text = text.replace(i, j)
    return text

def _parse_bibtex_entries(entries):
    biblio_list = []
    for entry in entries:
        stream = StringIO(entry)
        parser = bibtex.Parser()
        try:
            biblio = parser.parse_stream(stream)
            biblio_list += [biblio]
        except (PybtexSyntaxError, PybtexError), error:
            error = error
            print format_error(error, prefix='BIBTEX_ERROR: ')
            #logger.error("BIBTEX_ERROR error input: '{entry}'".format(
            #    entry=entry))
            #raise ProviderContentMalformedError(error.message)
    return biblio_list

def parse(bibtex_contents):
    enable_strict_mode(True) #throw errors
    ret = []
    cleaned_string = bibtex_contents.replace("\&", "").replace("%", "").strip()
    entries = ["@"+entry for entry in cleaned_string.split("@") if entry]
    biblio_list = _parse_bibtex_entries(entries)

    for biblio in biblio_list:
        parsed = {}
        try:
            mykey = biblio.entries.keys()[0]
        except AttributeError:
            # doesn't seem to be a valid biblio object, so skip to the next one
            print "NO DOI because no entries attribute"
            continue

        try:
            parsed["journal"] = _to_unicode(biblio.entries[mykey].fields["journal"])
        except KeyError:
            pass

        try:
            lnames = [person.get_part_as_text("last") for person in biblio.entries[mykey].persons["author"]]
            parsed["authors"] = _to_unicode(", ".join(lnames))
        except (KeyError, AttributeError):
            pass

        try:
            year_string = biblio.entries[mykey].fields["year"].replace("{}", "")
            parsed["year"] = re.sub("\D", "", year_string)
        except KeyError:
            pass

        try:
            parsed["title"] = _to_unicode(biblio.entries[mykey].fields["title"])
        except KeyError:
            pass

        #parsed["key"] = mykey

        ret.append(parsed)

    return ret
