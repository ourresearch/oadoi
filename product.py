from util import elapsed
from time import time




def get_oa_url(url):

    """
    first test, on SelectedWorks site for ethan:

    https://works.bepress.com/ethan_white/45/
    https://works.bepress.com/ethan_white/45/download/

    https://works.bepress.com/ethan_white/27/
    None
    """



class Tests(object):
    def run(self):
        start = time()

        self.passed = [1,2,3]
        self.failed = [4,5,6]
        self.count = len(self.passed) + len(self.failed)
        self.elapsed = elapsed(start)


