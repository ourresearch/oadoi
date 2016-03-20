from collections import defaultdict

from models.badge import Badge
from models.country import country_info
from models.country import get_name_from_iso
from models.country import pacific_rim_east, pacific_rim_west
from models.source import sources_metadata

def all_badge_assigners():
    resp = BadgeAssigner.__subclasses__()
    resp.sort(key=lambda x: x.group)
    return resp

def badge_configs_without_functions():
    resp = {}
    for subclass in all_badge_assigners():
        resp[subclass.__name__] = subclass.config_dict()
    return resp


class BadgeAssigner(object):
    display_name = ""
    level = "bronze"
    is_for_products = True
    group = None
    description = None
    extra_description = None
    img_url = None
    video_url = None
    credit = None

    def __init__(self):
        self.candidate_badge = Badge(name=self.__class__.__name__)
        self.assigned = False

    @property
    def name(self):
        return self.__class__.__name__

    def get_badge_or_None(self, person):
        self.decide_if_assigned(person)
        if self.assigned:
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
            "description": cls.description,
            "extra_description": cls.extra_description,
            "img_url": cls.img_url,
            "video_url": cls.video_url,
            "credit": cls.credit
        }
        return resp


# class open_science_triathalete(BadgeAssigner):
#     display_name = "Open Science triathalete"
#     level = "gold"
#     is_for_products = False
#     group = "depsy_score"
#     description = "You have open access articles, datasets, and software"
#
#     def decide_if_assigned(self, person):
#         has_software = person.depsy_id is not None
#         has_data = len([p.type=="dataset" for p in person.products]) > 0
#         has_open_article = len([p.is_oa_article for p in person.products]) > 0
#         if has_software and has_data and has_open_article:
#             self.assigned = True


class depsy_creator(BadgeAssigner):
    display_name = "Depsy creator"
    level = "bronze"
    is_for_products = False
    group = "depsy_score"
    description = "You have a Depsy software impact score!"

    def decide_if_assigned(self, person):
        if person.depsy_percentile:
            self.assigned = True
            self.candidate_badge.support = u"You are in the {} percentile <a href='http://depsy.org/person/{}'>on Depsy</a>.".format(
                round(person.depsy_percentile * 100, 0),
                person.depsy_id
            )

class depsy_maven(BadgeAssigner):
    display_name = "Depsy maven"
    level = "silver"
    is_for_products = False
    group = "depsy_score"
    description = "Your software impact is in the top 50 percent of all research software creators on Depsy"

    def decide_if_assigned(self, person):
        if person.depsy_percentile and person.depsy_percentile > 0.50:
            self.assigned = True
            self.candidate_badge.support = u"You are in the {} percentile <a href='http://depsy.org/person/{}'>on Depsy</a>.".format(
                round(person.depsy_percentile * 100, 0),
                person.depsy_id
            )

class depsy_genius(BadgeAssigner):
    display_name = "Depsy genius"
    level = "gold"
    is_for_products = False
    group = "depsy_score"
    description = "Your software impact  is in the top 25 percent of all research software creators on Depsy"

    def decide_if_assigned(self, person):
        if person.depsy_percentile and person.depsy_percentile > 0.75:
            self.assigned = True
            self.candidate_badge.support = u"You are in the {} percentile <a href='http://depsy.org/person/{}'>on Depsy</a>.".format(
                round(person.depsy_percentile * 100, 0),
                person.depsy_id
            )



class one_hit_wonder(BadgeAssigner):
    display_name = "One-hit wonder"
    level = "bronze"
    is_for_products = True
    group = "product_score_one_hit"
    description = "Your online impact score comes primarily from one research product"

    def decide_if_assigned(self, person):
        for my_product in person.products:
            if my_product.altmetric_score > 0.75*person.altmetric_score:
                self.assigned = True
                self.candidate_badge.add_product(my_product)


class baby_steps(BadgeAssigner):
    display_name = "Baby steps"
    level = "bronze"
    is_for_products = True
    group = "product_score_any"
    description = "You have made online impact!  Congrats!"

    def decide_if_assigned(self, person):
        for my_product in person.products:
            if my_product.altmetric_score > 0:
                self.assigned = True
                self.candidate_badge.add_product(my_product)


class megahit(BadgeAssigner):
    display_name = "Megahit"
    level = "gold"
    is_for_products = True
    group = "product_score_high"
    description = "You have a product with an Altmetric.com score of more than 100."

    def decide_if_assigned(self, person):
        for my_product in person.products:
                if my_product.altmetric_score > 100:
                    self.assigned = True
                    self.candidate_badge.add_product(my_product)


class third_time_charm(BadgeAssigner):
    display_name = "Third time charm"
    level = "bronze"
    is_for_products = True
    group = "product_score"
    description = "You have at least three products that have made impact."

    def decide_if_assigned(self, person):
        num_with_posts = 0
        for my_product in person.products:
            if my_product.altmetric_score > 0:
                num_with_posts += 1
                self.candidate_badge.add_product(my_product)
        if num_with_posts >= 3:
            self.assigned = True



class clean_sweep(BadgeAssigner):
    display_name = "Clean sweep"
    level = "silver"
    is_for_products = True
    group = "product_score"
    description = "All of your publications since 2012 have made impact."

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


class big_in_japan(BadgeAssigner):
    display_name = "Big in Japan"
    level = "bronze"
    is_for_products = True
    group = "geo_japan"
    description = "You made impact in Japan!"
    video_url = "https://www.youtube.com/watch?v=tl6u2NASUzU"
    credit = 'Alphaville - "Big In Japan"'

    def decide_if_assigned(self, person):
        for my_product in person.products:
            if my_product.has_country("Japan"):
                self.candidate_badge.add_product(my_product)
                self.assigned = True

class global_reach(BadgeAssigner):
    display_name = "Global reach"
    level = "bronze"
    is_for_products = False
    group = "geo_countries"
    description = "Your research has made an impact in more than 25 countries"

    def decide_if_assigned(self, person):
        if len(person.countries) > 25:
            self.assigned = True
            self.candidate_badge.support = u"Countries include: {}.".format(", ".join(person.countries))
            # print self.candidate_badge.support



class pacific_rim(BadgeAssigner):
    display_name = "Pacific rim"
    level = "silver"
    is_for_products = True
    group = "geo_pacific_rim"
    description = "You have impact from at least three eastern Pacific Rim and three western Pacific Rim countries."

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


class global_south(BadgeAssigner):
    display_name = "Global South"
    level = "gold"
    is_for_products = True
    group = "geo_global_south"
    description = "More than 25% of your impact is from the Global South."

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
                        print u"Nothing in dict for country name {}".format(country_name)
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


class ivory_tower(BadgeAssigner):
    display_name = "Ivory Tower"
    level = "bronze"
    is_for_products = False
    group = "poster_types"
    description = "More than 50% of your impact is from other researchers."

    def decide_if_assigned(self, person):
        proportion = proportion_poster_counts_by_type(person, "Scientists")
        if proportion > 0.50:
            self.assigned = True


class practical_magic(BadgeAssigner):
    display_name = "Practical Magic"
    level = "bronze"
    is_for_products = False
    group = "poster_types"
    description = "More than 10% of your impact is from practitioners."

    def decide_if_assigned(self, person):
        proportion = proportion_poster_counts_by_type(person, "Practitioners (doctors, other healthcare professionals)")
        if proportion > 0.10:
            self.assigned = True



class press_pass(BadgeAssigner):
    display_name = "Press pass"
    level = "bronze"
    is_for_products = False
    group = "poster_types"
    description = "More than 10% of your impact is from science communicators."

    def decide_if_assigned(self, person):
        proportion = proportion_poster_counts_by_type(person, "Science communicators (journalists, bloggers, editors)")
        if proportion > 0.10:
            self.assigned = True



class good_for_teaching(BadgeAssigner):
    display_name = "Good for teaching"
    level = "bronze"
    is_for_products = True
    group = "f1000_type"
    description = "Cool! An F1000 reviewer called your research good for teaching"

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
    level = "bronze"
    is_for_products = True
    group = "f1000_type"
    description = "Cool! An F1000 reviewer called your research a New Finding!"

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

class controversial(BadgeAssigner):
    display_name = "Controversial"
    level = "bronze"
    is_for_products = True
    group = "f1000_type"
    description = "Cool! An F1000 reviewer called your research Controversial!"

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

class publons(BadgeAssigner):
    display_name = "Publons star"
    level = "bronze"
    is_for_products = True
    group = "sources_publons"
    description = "Your research has a great score on Publons!"

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


class wiki_hit(BadgeAssigner):
    display_name = "Wiki hit"
    level = "bronze"
    is_for_products = False
    group = "sources_wiki"
    description = "Your research is mentioned in a Wikipedia article!"
    extra_description = "Wikipedia is referenced by <a href='http://www.theatlantic.com/health/archive/2014/03/doctors-1-source-for-healthcare-information-wikipedia/284206/'>half of doctors!</a>"

    def decide_if_assigned(self, person):
        if person.post_counts_by_source("wikipedia") >= 1:
            self.assigned = True
            urls = person.wikipedia_urls
            self.candidate_badge.add_products([p for p in person.products if p.has_source("wikipedia")])
            self.candidate_badge.support = u"Wikipedia titles include: {}.".format(
                ", ".join(urls))
            # print self.candidate_badge.support

class wiki_star(BadgeAssigner):
    display_name = "Wiki star"
    level = "silver"
    is_for_products = False
    group = "sources_wiki"
    description = "Your research is mentioned in more than 5 Wikipedia articles!"

    def decide_if_assigned(self, person):
        if person.post_counts_by_source("wikipedia") >= 5:
            self.assigned = True
            urls = person.wikipedia_urls
            self.candidate_badge.add_products([p for p in person.products if p.has_source("wikipedia")])
            self.candidate_badge.support = u"Wikipedia titles include: {}.".format(
                ", ".join(urls))

class wiki_superstar(BadgeAssigner):
    display_name = "Wiki superstar"
    level = "gold"
    is_for_products = False
    group = "sources_wiki"
    description = "Your research is mentioned in more than 10 Wikipedia articles!"

    def decide_if_assigned(self, person):
        if person.post_counts_by_source("wikipedia") >= 10:
            self.assigned = True
            urls = person.wikipedia_urls
            self.candidate_badge.add_products([p for p in person.products if p.has_source("wikipedia")])
            self.candidate_badge.support = u"Wikipedia titles include: {}.".format(
                ", ".join(urls))


class unicorn(BadgeAssigner):
    display_name = "Unicorn"
    level = "bronze"
    is_for_products = True
    group = "sources_rare"
    description = "You made impact in a rare place"

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


class deep_interest(BadgeAssigner):
    display_name = "Deep interest"
    level = "silver"
    is_for_products = True
    group = "sources_ratio"
    description = "People are deeply interested in your research.  There is a high ratio of (news + blogs) / (twitter + facebook)"
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



class everywhere(BadgeAssigner):
    display_name = "Everywhere"
    level = "gold"
    is_for_products = False
    group = "sources_number"
    description = "You have made impact on at least 10 channels. You are everywhere!"
    video_url = "https://www.youtube.com/watch?v=FsglRLoUdtc"
    credit = "Fleetwood Mac: Everywhere"

    def decide_if_assigned(self, person):
        if person.num_sources >= 10:
            self.assigned = True


class at_every_turn(BadgeAssigner):
    display_name = "At every turn"
    level = "silver"
    is_for_products = False
    group = "sources_number"
    description = "You have made impact on at least 7 channels. You are blanketing the airwaves!"

    def decide_if_assigned(self, person):
        if person.num_sources >= 7:
            self.assigned = True


class talk_of_the_town(BadgeAssigner):
    display_name = "Talk of the town"
    level = "bronze"
    is_for_products = False
    group = "sources_number"
    description = "You have made impact on at least 5 channels."

    def decide_if_assigned(self, person):
        if person.num_sources >= 5:
            self.assigned = True


class rick_roll(BadgeAssigner):
    display_name = "Rickroll"
    level = "bronze"
    is_for_products = True
    group = "fan_rick"
    description = "You have been tweeted by a person named Richard!"
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

        if self.assigned:
            print "RICK!!!!", self.candidate_badge.support


class megafan(BadgeAssigner):
    display_name = "Megafan"
    level = "silver"
    is_for_products = True
    group = "fan_big"
    description = "Someone with more than 10k followers has tweeted your research."

    def decide_if_assigned(self, person):
        fans = set()

        for my_product in person.products:
            for fan_name, followers in my_product.twitter_posters_with_followers.iteritems():
                if followers >= 50000:
                    self.assigned = True
                    self.candidate_badge.add_product(my_product)
                    fans.add(fan_name)

        fan_urls = [u"<a href='http://twitter.com/{fan}'>@{fan}</a>".format(fan=fan) for fan in fans]
        self.candidate_badge.support = u"Megafans include: {}".format(u",".join(fans))




class bff(BadgeAssigner):
    display_name = "bff"
    level = "silver"
    is_for_products = False
    group = "tweeters_count"
    description = "You have a BFF! Someone has tweeted three or more of your papers."

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



class babel(BadgeAssigner):
    display_name = "Babel"
    level = "bronze"
    is_for_products = False
    group = "geo_languages"
    description = "Your impact is in more than just English!"
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
            print self.candidate_badge.support


# inspired by https://github.com/ThinkUpLLC/ThinkUp/blob/db6fbdbcc133a4816da8e7cc622fd6f1ce534672/webapp/plugins/insightsgenerator/insights/followcountvisualizer.php
class lincoln_center(BadgeAssigner):
    display_name = "Lincoln Center"
    level = "bronze"
    is_for_products = False
    group = "impressions"
    description = "The number of twitter impressions your work would fill Lincoln Center!"
    img_url = "https://en.wikipedia.org/wiki/File:Avery_fisher_hall.jpg"
    credit = "Photo: Mikhail Klassen"

    def decide_if_assigned(self, person):
        if person.impressions >= 2740:
            self.assigned = True

# inspired by https://github.com/ThinkUpLLC/ThinkUp/blob/db6fbdbcc133a4816da8e7cc622fd6f1ce534672/webapp/plugins/insightsgenerator/insights/followcountvisualizer.php
class yankee_stadium(BadgeAssigner):
    display_name = "Yankee Stadium"
    level = "silver"
    is_for_products = False
    group = "impressions"
    description = "The number of twitter impressions your work would fill Yankee Stadium!"
    img_url = "https://www.thinkup.com/assets/images/insights/2014-05/yankeestadium.jpg"
    credit = "Photo: Shawn Collins"

    def decide_if_assigned(self, person):
        if person.impressions >= 50000:
            self.assigned = True

# inspired by https://github.com/ThinkUpLLC/ThinkUp/blob/db6fbdbcc133a4816da8e7cc622fd6f1ce534672/webapp/plugins/insightsgenerator/insights/followcountvisualizer.php
class woodstock(BadgeAssigner):
    display_name = "Woodstock"
    level = "gold"
    is_for_products = False
    group = "impressions"
    description = "The number of twitter impressions your work is larger than the number of people who went to Woodstock!"
    img_url = "http://fi.wikipedia.org/wiki/Woodstock#mediaviewer/Tiedosto:Swami_opening.jpg"
    credit = "Photo: Mark Goff"

    def decide_if_assigned(self, person):
        if person.impressions >= 500000:
            self.assigned = True


class url_soup(BadgeAssigner):
    display_name = "URL soup"
    level = "bronze"
    is_for_products = True
    group = "misc_urls"
    description = "You have a research product that has made impact under more than 20 urls"

    def decide_if_assigned(self, person):
        for my_product in person.products:
            if len(my_product.impact_urls) > 20:
                self.assigned = True
                self.candidate_badge.add_product(my_product)
                self.candidate_badge.support = u"URLs for one of the products include: {}".format(
                    ", ".join(sorted(my_product.impact_urls))
                )


