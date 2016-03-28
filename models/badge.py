from collections import defaultdict

from models.country import country_info
from models.country import get_name_from_iso
from models.country import pacific_rim_east, pacific_rim_west
from models.source import sources_metadata
from models.scientist_stars import scientists_twitter


from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db
from util import date_as_iso_utc

import datetime
import shortuuid

def all_badge_assigners():
    resp = BadgeAssigner.__subclasses__()
    resp.sort(key=lambda x: x.group)
    return resp

def badge_configs_without_functions():
    resp = {}
    for subclass in all_badge_assigners():
        resp[subclass.__name__] = subclass.config_dict()
    return resp


class BadgeRareness(db.Model):
    __table__ = db.Table(
        "badge_rareness",
        db.metadata,
        db.Column("name", db.Text, db.ForeignKey("badge.name"), primary_key=True),
        db.Column("percent_of_people", db.Float),
        autoload=True,
        autoload_with=db.engine
    )


class Badge(db.Model):
    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text)
    level = db.Column(db.Float)
    orcid_id = db.Column(db.Text, db.ForeignKey('person.orcid_id'))
    created = db.Column(db.DateTime)
    support = db.Column(db.Text)
    products = db.Column(MutableDict.as_mutable(JSONB))
    rareness_row = db.relationship(
        'BadgeRareness',
        lazy='subquery',
        foreign_keys="BadgeRareness.name"
    )

    def __init__(self, assigned=True, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow().isoformat()
        self.assigned = assigned
        self.products = {}
        super(Badge, self).__init__(**kwargs)

    @property
    def rareness(self):
        if self.rareness_row:
            return self.rareness_row[0].percent_of_people
        else:
            return 0


    @property
    def dois(self):
        if self.products:
            return self.products.keys()
        return []

    @property
    def num_products(self):
        if self.products:
            return len(self.products)
        else:
            return 0

    def add_product(self, my_product):
        self.products[my_product.doi] = True


    def add_products(self, products_list):
        for my_product in products_list:
            self.add_product(my_product)


    def __repr__(self):
        return u'<Badge ({id} {name} {level})>'.format(
            id=self.id,
            name=self.name,
            level=self.level
        )

    def to_dict(self):
        if self.products:
            product_list = self.products.keys()

        configs = badge_configs_without_functions()

        if self.name in configs:
            resp = configs[self.name]
            try:
                description = configs[self.name]["descriptions"][self.level]
            except KeyError:
                description = "no description given"

            resp_extra =  {
                "id": self.id,
                "name": self.name,
                "created": date_as_iso_utc(self.created),
                "num_products": self.num_products,
                "rareness": round(self.rareness, 2),
                "support": self.support,
                # "next_level": self.next_level,
                "level": self.level,
                "max_level": max(configs[self.name]["descriptions"].keys()),
                "description": description,
                "dois": self.dois
            }
            resp.update(resp_extra)
        else:
            resp = {}
        return resp



class BadgeAssigner(object):
    display_name = ""
    level = 1
    is_for_products = True
    group = None
    description = {1: ""}
    extra_description = None
    img_url = None
    video_url = None
    credit = None
    next_level = None

    def __init__(self):
        self.candidate_badge = Badge(name=self.__class__.__name__)
        self.assigned = False

    @property
    def name(self):
        return self.__class__.__name__

    def get_badge_or_None(self, person):
        self.decide_if_assigned(person)
        if self.assigned:
            self.candidate_badge.level = self.level
            try:
                self.candidate_badge.description = self.descriptions[self.level]
            except KeyError:
                self.candidate_badge.description = "no description given"
            return self.candidate_badge
        return None

    #override this in subclasses
    def decide_if_assigned(self, person):
        return None

    @classmethod
    def config_dict(cls):
        resp = {
            "name": cls.__name__,
            "display_name": cls.display_name,
            "level": cls.level,
            "is_for_products": cls.is_for_products,
            "group": cls.group,
            "descriptions": cls.descriptions,
            "extra_description": cls.extra_description,
            "img_url": cls.img_url,
            "video_url": cls.video_url,
            "credit": cls.credit
        }
        return resp



# 0.18204108320165599	1
# 0.373344957227701002	2
# 0.434860785702609998	3
# 0.698632376178281	4
# 0.878112570152019045	5
# 0.938375197515393	6
# 0.965836647959462002	7
# 0.98910259903013098	8
# 0.993298098403531005	9
# 0.994660273524764049	10

# with nulls removed

# 0.18204108320165599	1
# 0.373344957227701002	2
# 0.434860785702609998	3
# 0.698632376178281	4
# 0.878112570152019045	5
# 0.938375197515393	6
# 0.965836647959462002	7
# 0.98910259903013098	8
# 0.993298098403531005	9
# 0.994660273524764049	10

class depsy(BadgeAssigner):
    display_name = "Software reuse"
    is_for_products = False
    group = "channels"
    descriptions = {
        1: "You have a Depsy software impact score!",
        2: "Your software impact is in the top 50 percent of all research software creators on Depsy",
        3: "Your software impact  is in the top 25 percent of all research software creators on Depsy"
    }

    def decide_if_assigned(self, person):
        if person.depsy_percentile:
            thesholds = {
                1: 0,
                2: .25,
                3: .50,
                4: .75,
                5: .90
            }
            my_level = 0
            my_threshold = 0

            for (test_level, test_threshold) in thesholds.iteritems():
                if test_level > self.level:
                    if person.depsy_percentile > test_threshold:
                        self.level = test_level
                        self.assigned = True
                        self.candidate_badge.support = u"You are in the {} percentile <a href='http://depsy.org/person/{}'>on Depsy</a>.".format(
                            round(person.depsy_percentile * 100, 0),
                            person.depsy_id
                        )



class big_hit(BadgeAssigner):
    display_name = "Big Hit"
    is_for_products = True
    group = "reach"
    descriptions = {
        1: "You have a product with an Altmetric.com score of more than 50.",
        2: "You have a product with an Altmetric.com score of more than 100.",
        3: "You have a product with an Altmetric.com score of more than 250.",
    }

    def decide_if_assigned(self, person):
        thesholds = {
            1: 10,
            2: 50,
            3: 100,
            4: 250,
            5: 500
        }
        max_altmetric_score = max([p.altmetric_score for p in person.products])
        my_level = 0
        my_threshold = 0

        for (test_level, test_threshold) in thesholds.iteritems():
            if test_level > my_level:
                if max_altmetric_score > test_threshold:
                    my_level = test_level
                    my_threshold = test_threshold
                    self.assigned = True

        if self.assigned:
            self.level = my_level
            for my_product in person.products:
                if my_product.altmetric_score > my_threshold:
                    self.candidate_badge.add_product(my_product)


# select min(i), decade from
# (select coalesce((post_counts->>'wikipedia')::int, 0) as i,
# ntile(10) over (order by coalesce((post_counts->>'wikipedia')::int, 0)) as decade
# from person
# where (campaign = 'impactstory_nos' or campaign = 'impactstory_subscribers')
# order by coalesce((post_counts->>'wikipedia')::int, 0) )
# s
# group by decade
# order by decade

# 0	1
# 0	2
# 0	3
# 0	4
# 0	5
# 1	6
# 1	7
# 3	8
# 4	9
# 9	10

class wiki_hit(BadgeAssigner):
    display_name = "Wiki hit"
    is_for_products = False
    group = "channels"
    descriptions = {
        1: "Your research is mentioned in a Wikipedia article!",
        2: "Your research is mentioned in more than 5 Wikipedia articles!",
        3: "Your research is mentioned in more than 10 Wikipedia articles!"
    }
    extra_description = "Wikipedia is referenced by <a href='http://www.theatlantic.com/health/archive/2014/03/doctors-1-source-for-healthcare-information-wikipedia/284206/'>half of doctors!</a>"

    def decide_if_assigned(self, person):
        thesholds = {
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5
        }
        max_altmetric_score = max([p.altmetric_score for p in person.products])
        my_level = 0
        my_threshold = 0

        num_wikipedia_posts = person.post_counts_by_source("wikipedia")
        for (test_level, test_threshold) in thesholds.iteritems():
            if test_level > my_level:
                if num_wikipedia_posts > test_threshold:
                    my_level = test_level
                    my_threshold = test_threshold
                    self.assigned = True

        if self.assigned:
            self.level = my_level
            urls = person.wikipedia_urls
            self.candidate_badge.add_products([p for p in person.products if p.has_source("wikipedia")])
            self.candidate_badge.support = u"Wikipedia titles include: {}.".format(
                ", ".join(urls))
            # print self.candidate_badge.support

# 1	1
# 3	2
# 4	3
# 4	4
# 5	5
# 5	6
# 6	7
# 7	8
# 7	9
# 9	10

class everywhere(BadgeAssigner):
    display_name = "Everywhere"
    is_for_products = False
    group = "channels"
    descriptions = {
        1: "You have made impact on at least 5 channels. You are everywhere!",
        2: "You have made impact on at least 7 channels. You are everywhere!",
        3: "You have made impact on at least 10 channels. You are everywhere!"
    }
    video_url = "https://www.youtube.com/watch?v=FsglRLoUdtc"
    credit = "Fleetwood Mac: Everywhere"

    def decide_if_assigned(self, person):
        thesholds = {
            1: 3,
            2: 4,
            3: 5,
            4: 6,
            5: 7
        }
        for (test_level, test_threshold) in thesholds.iteritems():
            if test_level > self.level:
                if person.num_sources > test_threshold:
                    self.level = test_level
                    self.assigned = True


# 0	1
# 19134	2
# 35579	3
# 60996	4
# 91346	5
# 138575	6
# 186199	7
# 299688	8
# 495392	9
# 868292	10

# inspired by https://github.com/ThinkUpLLC/ThinkUp/blob/db6fbdbcc133a4816da8e7cc622fd6f1ce534672/webapp/plugins/insightsgenerator/insights/followcountvisualizer.php
class impressions(BadgeAssigner):
    display_name = "You make an impression"
    is_for_products = False
    group = "reach"
    descriptions = {
        1: "The number of twitter impressions your work would fill Lincoln Center!",
        2: "The number of twitter impressions your work would fill Yankee Stadium!",
        3: "The number of twitter impressions your work is larger than the number of people who went to Woodstock!"
    }
    img_url = "https://en.wikipedia.org/wiki/File:Avery_fisher_hall.jpg"
    credit = "Photo: Mikhail Klassen"

    def decide_if_assigned(self, person):
        thesholds = {
            1: 2740,  #almost everyone
            2: 25000,
            3: 50000,
            4: 250000,
            5: 500000 #top 20 percent
        }
        for (test_level, test_threshold) in thesholds.iteritems():
            if test_level > self.level:
                if person.impressions > test_threshold:
                    self.level = test_level
                    self.assigned = True


#### not yet multiples

class long_legs(BadgeAssigner):
    display_name = "Long Legs"
    level = 1
    is_for_products = True
    group = "timeline"
    descriptions = {1: "Your research received news or blog mentions more than 2 years after it was published"}

    def decide_if_assigned(self, person):
        for my_product in person.products:
            for source, days_since_pub in my_product.event_days_since_publication.iteritems():
                if source in ["news", "blogs"]:
                    events_after_two_years = [e for e in days_since_pub if e > 2*365]
                    if len(events_after_two_years) > 0:
                        self.assigned = True
                        self.candidate_badge.add_product(my_product)



class hot_streak(BadgeAssigner):
    display_name = "Hot streak"
    level = 1
    is_for_products = False
    group = "timeline"
    descriptions = {1: "You made an impact in each of the last 12 months"}

    def decide_if_assigned(self, person):
        streak = True
        for month in range(0, 12):
            matching_days_count = 0
            for source, days_ago in person.all_event_days_ago.iteritems():
                relevant_days = [month*30 + day for day in range(0, 30)]
                matching_days_count += len([d for d in days_ago if d in relevant_days])

            if matching_days_count <= 0:
                # print "broke the streak on month", month
                streak = False
        if streak:
            self.assigned = True




class deep_interest(BadgeAssigner):
    display_name = "Deep interest"
    level = 1
    is_for_products = True
    group = "channels"
    descriptions = {1: "People are deeply interested in your research.  There is a high ratio of (news + blogs) / (twitter + facebook)"}
    extra_description = "Based on papers published since 2012 that have more than 10 relevant posts."

    def decide_if_assigned(self, person):
        for my_product in person.products:
            longform_posts = 0.0
            shortform_posts = 0.0

            if my_product.year_int > 2011:
                longform_posts += my_product.post_counts_by_source("news")
                longform_posts += my_product.post_counts_by_source("blogs")
                shortform_posts += my_product.post_counts_by_source("twitter")
                shortform_posts += my_product.post_counts_by_source("facebook")

            if (shortform_posts > 0) and (longform_posts+shortform_posts > 10):
                ratio = longform_posts / shortform_posts
                # print u"deep-interest ratio: ", ratio
                if ratio > 0.10:
                    self.assigned = True
                    self.candidate_badge.add_product(my_product)


class clean_sweep(BadgeAssigner):
    display_name = "Clean sweep"
    level = 1
    is_for_products = False
    group = "timeline"
    descriptions = {1: "All of your publications since 2012 have made impact."}

    def decide_if_assigned(self, person):
        num_with_posts = 0
        num_applicable = 0
        for my_product in person.products:
            if my_product.year > 2011:
                num_applicable += 1
                if my_product.altmetric_score > 0:
                    num_with_posts += 1
                    self.candidate_badge.add_product(my_product)

        if num_with_posts >= num_applicable:
            self.assigned = True



class global_reach(BadgeAssigner):
    display_name = "Global reach"
    level = 1
    is_for_products = False
    group = "geo"
    descriptions = {1: "Your research has made an impact in more than 25 countries"}

    def decide_if_assigned(self, person):
        if len(person.countries) > 25:
            self.assigned = True
            self.candidate_badge.support = u"Countries include: {}.".format(", ".join(person.countries))
            # print self.candidate_badge.support





class global_south(BadgeAssigner):
    display_name = "Global South"
    level = 1
    is_for_products = True
    group = "geo"
    descriptions = {1: "More than 25% of your impact is from the Global South."}

    def decide_if_assigned(self, person):
        countries = []

        total_geo_located_posts = 0.0
        total_global_south_posts = 0.0

        for my_product in person.products:
            for country_iso, count in my_product.post_counts_by_country.iteritems():
                total_geo_located_posts += count
                country_name = get_name_from_iso(country_iso)
                if country_name:
                    try:
                        if country_info[country_name]["is_global_south"]:
                            total_global_south_posts += count
                            self.candidate_badge.add_product(my_product)
                            countries.append(country_name)
                    except KeyError:
                        print u"ERROR: Nothing in dict for country name {}".format(country_name)
                        raise # don't keep going

        if total_geo_located_posts > 0:
            # print u"PERCENT GLOBAL SOUTH {} / {} = {}".format(
            #     total_global_south_posts,
            #     total_geo_located_posts,
            #     (total_global_south_posts / total_geo_located_posts)
            # )
            # print u"global south countries: {}".format(countries)

            if (total_global_south_posts / total_geo_located_posts) > 0.25:
                self.assigned = True
                self.candidate_badge.support = "Impact from these Global South countries: {}.".format(
                    ", ".join(countries))



class famous_follower(BadgeAssigner):
    display_name = "Famous follower"
    level = 1
    is_for_products = True
    group = "audience"
    descriptions = {1: "You have been tweeted by a well-known scientist"}

    def decide_if_assigned(self, person):
        fans = set()
        for my_product in person.products:
            for twitter_handle in my_product.twitter_posters_with_followers:
                if twitter_handle.lower() in scientists_twitter:
                    fans.add(twitter_handle)
                    self.assigned = True
                    self.candidate_badge.add_product(my_product)

        # if self.assigned:
        fan_urls = [u"<a href='http://twitter.com/{fan}'>@{fan}</a>".format(fan=fan) for fan in fans]
        self.candidate_badge.support = u"Famous fans include: {}".format(u",".join(fan_urls))




class megafan(BadgeAssigner):
    display_name = "Megafan"
    level = 1
    is_for_products = True
    group = "audience"
    descriptions = {1: "Someone with more than 10k followers has tweeted your research."}

    def decide_if_assigned(self, person):
        fans = set()

        for my_product in person.products:
            for fan_name, followers in my_product.twitter_posters_with_followers.iteritems():
                if followers >= 50000:
                    self.assigned = True
                    self.candidate_badge.add_product(my_product)
                    fans.add(fan_name)

        fan_urls = [u"<a href='http://twitter.com/{fan}'>@{fan}</a>".format(fan=fan) for fan in fans]
        self.candidate_badge.support = u"Megafans include: {}".format(u",".join(fan_urls))






class babel(BadgeAssigner):
    display_name = "Babel"
    level = 1
    is_for_products = False
    group = "audience"
    descriptions = {1: "Your impact is in more than just English!"}
    extra_description = "Due to issues with the Twitter API, we don't have language information for tweets yet."

    def decide_if_assigned(self, person):
        languages_with_examples = {}

        for my_product in person.products:
            languages_with_examples.update(my_product.languages_with_examples)
            if len(set(my_product.languages_with_examples.keys()) - set(["en"])) > 0:
                self.assigned = True
                self.candidate_badge.add_product(my_product)

        if self.assigned:
            language_url_list = [u"{} (<a href='{}'>example</a>)".format(lang, url)
                 for (lang, url) in languages_with_examples.iteritems()]
            self.candidate_badge.support = u"Langauges: {}".format(u", ".join(language_url_list))
            # print self.candidate_badge.support



class unicorn(BadgeAssigner):
    display_name = "Unicorn"
    level = 1
    is_for_products = True
    group = "channels"
    descriptions = {1: "You made impact in a rare place"}

    def decide_if_assigned(self, person):
        sources = set()
        for my_product in person.products:
            if my_product.post_counts:
                for (source_name, post_count) in my_product.post_counts.iteritems():
                    if post_count > 0:
                        if source_name in ["linkedin", "peer_review", "pinterest", "q&a", "video", "weibo"]:
                            self.assigned = True
                            self.candidate_badge.add_product(my_product)
                            sources.add(source_name)
        if self.assigned:
            self.candidate_badge.support = u"Your rare sources include: {}".format(
                ", ".join(sorted(sources))
            )
            # print self.candidate_badge.support


#############
# SINGLES
#############



class pacific_rim(BadgeAssigner):
    display_name = "Pacific rim"
    level = 1
    is_for_products = True
    group = "geo"
    descriptions = {1: "You have impact from at least three eastern Pacific Rim and three western Pacific Rim countries."}

    def decide_if_assigned(self, person):
        countries = []

        num_pacific_rim_west = 0
        for country in pacific_rim_west:
            matching_products = [p for p in person.products if p.has_country(country)]
            if matching_products:
                num_pacific_rim_west += 1
                self.candidate_badge.add_products(matching_products)
                countries.append(country)

        num_pacific_rim_east = 0
        for country in pacific_rim_east:
            matching_products = [p for p in person.products if p.has_country(country)]
            if matching_products:
                num_pacific_rim_east += 1
                self.candidate_badge.add_products(matching_products)
                countries.append(country)

        if num_pacific_rim_west >= 3 and num_pacific_rim_east >= 3:
            self.assigned = True
            self.candidate_badge.support = "Impact from these Pacific Rim countries: {}.".format(
                ", ".join(countries))
            # print u"badge support: {}".format(self.candidate_badge.support)



class ivory_tower(BadgeAssigner):
    display_name = "Ivory Tower"
    level = 1
    is_for_products = False
    group = "audience"
    descriptions = {1: "More than 50% of your impact is from other researchers."}

    def decide_if_assigned(self, person):
        proportion = proportion_poster_counts_by_type(person, "Scientists")
        if proportion > 0.50:
            self.assigned = True


class practical_magic(BadgeAssigner):
    display_name = "Practical Magic"
    level = 1
    is_for_products = False
    group = "audience"
    descriptions = {1: "More than 10% of your impact is from practitioners."}

    def decide_if_assigned(self, person):
        proportion = proportion_poster_counts_by_type(person, "Practitioners (doctors, other healthcare professionals)")
        if proportion > 0.10:
            self.assigned = True

class press_pass(BadgeAssigner):
    display_name = "Press pass"
    level = 1
    is_for_products = False
    group = "audience"
    descriptions = {1: "More than 10% of your impact is from science communicators."}

    def decide_if_assigned(self, person):
        proportion = proportion_poster_counts_by_type(person, "Science communicators (journalists, bloggers, editors)")
        if proportion > 0.10:
            self.assigned = True


class sleeping_beauty(BadgeAssigner):
    display_name = "Sleeping beauty"
    level = 1
    is_for_products = True
    group = "timeline"
    descriptions = {1: "Your research picked up in activity after its first six months"}

    def decide_if_assigned(self, person):
        for my_product in person.products:
            events_with_dates = 0.0
            events_in_first_six_months = 0.0

            for source, days_since_pub in my_product.event_days_since_publication.iteritems():
                events_with_dates += len(days_since_pub)
                events_in_first_six_months += len([e for e in days_since_pub if e <= 180])

            if events_with_dates > 0:
                ratio = events_in_first_six_months / events_with_dates
                if ratio <= 0.5:
                    self.assigned = True
                    self.candidate_badge.add_product(my_product)


def proportion_poster_counts_by_type(person, poster_type):
    total_posters_with_type = 0.0
    ivory_tower_posters = 0.0
    for my_product in person.products:
        total_posters_with_type += sum(my_product.poster_counts_by_type.values())
        if poster_type in my_product.poster_counts_by_type:
            ivory_tower_posters += my_product.poster_counts_by_type[poster_type]

    if total_posters_with_type:
        return (ivory_tower_posters / total_posters_with_type)
    else:
        return 0


class good_for_teaching(BadgeAssigner):
    display_name = "Good for teaching"
    level = 1
    is_for_products = True
    group = "merit"
    descriptions = {1: "Cool! An F1000 reviewer called your research good for teaching"}

    def decide_if_assigned(self, person):
        urls = []
        for my_product in person.products:
            f1000_urls = my_product.f1000_urls_for_class("good_for_teaching")
            if f1000_urls:
                self.assigned = True
                self.candidate_badge.add_product(my_product)
                urls += f1000_urls

        if self.assigned:
            self.candidate_badge.support = u"The F1000 reviews include: {}.".format(
                ", ".join(urls))
            # print self.candidate_badge.support


class new_finding(BadgeAssigner):
    display_name = "New finding"
    level = 1
    is_for_products = True
    group = "merit"
    descriptions = {1: "Cool! An F1000 reviewer called your research a New Finding!"}

    def decide_if_assigned(self, person):
        urls = []
        for my_product in person.products:
            f1000_urls = my_product.f1000_urls_for_class("new_finding")
            if f1000_urls:
                self.assigned = True
                self.candidate_badge.add_product(my_product)
                urls += f1000_urls

        if self.assigned:
            self.candidate_badge.support = u"The F1000 reviews include: {}.".format(
                ", ".join(urls))
            # print self.candidate_badge.support



class publons(BadgeAssigner):
    display_name = "Publons star"
    level = 1
    is_for_products = True
    group = "merit"
    descriptions = {1: "Your research has a great score on Publons!"}

    def decide_if_assigned(self, person):
        reviews = []

        if person.post_counts_by_source("peer_reviews") >= 1:
            for my_product in person.products:
                for review in my_product.publons_reviews:
                    if review["publons_weighted_average"] > 5:
                        self.assigned = True
                        self.candidate_badge.add_product(my_product)
                        reviews.append(review)
        if self.assigned:
            review_urls = [u"<a href='{}'>Review</a>".format(review["url"]) for review in reviews]
            self.candidate_badge.support = u"Publons reviews: {}".format(", ".join(review_urls))


class first_steps(BadgeAssigner):
    display_name = "First steps"
    level = 1
    is_for_products = False
    group = "reach"
    descriptions = {
        1: "You have made online impact!  Congrats!"
    }

    def decide_if_assigned(self, person):
        for my_product in person.products:
            if my_product.altmetric_score > 0:
                self.assigned = True


#############
# FUN
#############

class url_soup(BadgeAssigner):
    display_name = "URL soup"
    level = 0
    is_for_products = True
    group = "fun"
    descriptions = {1: "You have a research product that has made impact under more than 20 urls"}

    def decide_if_assigned(self, person):
        for my_product in person.products:
            if len(my_product.impact_urls) > 20:
                self.assigned = True
                self.candidate_badge.add_product(my_product)
                self.candidate_badge.support = u"URLs for one of the products include: {}".format(
                    ", ".join(sorted(my_product.impact_urls))
                )


class bff(BadgeAssigner):
    display_name = "bff"
    level = 0
    is_for_products = False
    group = "fun"
    descriptions = {1: "You have a BFF! Someone has tweeted three or more of your papers."}

    def decide_if_assigned(self, person):
        fan_counts = defaultdict(int)
        fans = set()

        for my_product in person.products:
            for fan_name in my_product.twitter_posters_with_followers:
                fan_counts[fan_name] += 1

        for fan_name, tweeted_papers_count in fan_counts.iteritems():
            if tweeted_papers_count >= 3:
                self.assigned = True
                fans.add(fan_name)

        fan_urls = [u"<a href='http://twitter.com/{fan}'>@{fan}</a>".format(fan=fan) for fan in fans]
        self.candidate_badge.support = u"BFFs include: {}".format(u",".join(fan_urls))

class rick_roll(BadgeAssigner):
    display_name = "Rickroll"
    level = 0
    is_for_products = True
    group = "fun"
    descriptions = {1: "You have been tweeted by a person named Richard!"}
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def decide_if_assigned(self, person):
        for my_product in person.products:
            for name in my_product.tweeter_posters_full_names:
                match = False
                if name.lower().endswith("richard"):
                    match = True
                else:
                    for name_part in name.lower().split(" ")[:-1]:  # don't include last name
                        if name_part in ["rick", "rich", "ricky", "dick", "richard"]:
                            match = True
                if match:
                    self.assigned = True
                    self.candidate_badge.add_product(my_product)
                    self.candidate_badge.support = u"Thanks, {}".format(name)

        # if self.assigned:
        #     print "RICK!!!!", self.candidate_badge.support


class big_in_japan(BadgeAssigner):
    display_name = "Big in Japan"
    level = 1
    is_for_products = True
    group = "fun"
    descriptions = {1: "You made impact in Japan!"}
    video_url = "https://www.youtube.com/watch?v=tl6u2NASUzU"
    credit = 'Alphaville - "Big In Japan"'

    def decide_if_assigned(self, person):
        for my_product in person.products:
            if my_product.has_country("Japan"):
                self.candidate_badge.add_product(my_product)
                self.assigned = True


class controversial(BadgeAssigner):
    display_name = "Controversial"
    level = 1
    is_for_products = True
    group = "fun"
    descriptions = {1: "Cool! An F1000 reviewer called your research Controversial!"}

    def decide_if_assigned(self, person):
        urls = []
        for my_product in person.products:
            f1000_urls = my_product.f1000_urls_for_class("controversial")
            if f1000_urls:
                self.assigned = True
                self.candidate_badge.add_product(my_product)
                urls += f1000_urls

        if self.assigned:
            self.candidate_badge.support = u"The F1000 reviews include: {}.".format(
                ", ".join(urls))
            # print self.candidate_badge.support
