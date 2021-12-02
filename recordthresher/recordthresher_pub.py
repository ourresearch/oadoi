from pub import Pub


class RecordthresherPub(Pub):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._authors = None

    @property
    def authors(self):
        return self._authors

    @authors.setter
    def authors(self, authors):
        self._authors = authors

    @property
    def first_author_lastname(self):
        if self.authors:
            return self.authors[0].get('family')

        return None

    @property
    def last_author_lastname(self):
        if self.authors:
            return self.authors[-1].get('family')

        return None

    def __repr__(self):
        if self.id:
            my_string = self.id
        else:
            my_string = self.best_title
        return "<RecordthresherPub ( {} )>".format(my_string)

