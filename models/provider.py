
class ProviderError(Exception):
    def __init__(self, message="", inner=None):
        self._message = message  # naming it self.message raises DepreciationWarning
        self.inner = inner
        
    # DeprecationWarning: BaseException.message has been deprecated 
    #   as of Python 2.6 so implement property here
    @property
    def message(self): 
        return (self._message)

    def log(self):
        msg = " " + self.message + " " if self.message is not None and self.message != "" else ""
        wraps = "(inner exception: " + repr(self.inner) + ")"
        return self.__class__.__name__ + ":" + msg + wraps

    def __str__(self):
        return repr(self._message)


class ProviderClientError(ProviderError):
    def __init__(self, message="", inner=None):
        super(ProviderClientError, self).__init__(message, inner)

class ProviderContentMalformedError(ProviderClientError):
    pass

class ProviderContentNotFoundError(ProviderClientError):
    pass


def _lookup_json(data, keylist):
    for mykey in keylist:
        try:
            data = data[mykey]
        except (KeyError, TypeError):
            return None
    return(data)

def _extract_from_data_dict(data, dict_of_keylists, include_falses=False):
    return_dict = {}
    if dict_of_keylists:
        for (metric, keylist) in dict_of_keylists.iteritems():
            value = _lookup_json(data, keylist)

            # unless include_falses, only set metrics for non-zero and non-null metrics
            if include_falses or (value and (value != "0")):
                return_dict[metric] = value
    return return_dict


def extract_from_json(resp, dict_of_keylists, include_falses=False):
    data = resp.json()
    if not data:
        return {}
    return_dict = _extract_from_data_dict(data, dict_of_keylists, include_falses)

    return return_dict

