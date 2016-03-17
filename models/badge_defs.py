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
        resp[subclass.__name__] = subclass.config_dict
    return resp


class BadgeAssigner(object):
    display_name = ""
    level = "bronze"
    is_for_products = True
    group = None
    description = None
    extra_description = None

    def __init__(self):
        self.candidate_badge = Badge(name=self.name)
        self.assigned = False

    @property
    def name(self):
        return self.__name__

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
        }
        return resp


class big_in_japan(BadgeAssigner):
    display_name = "Big in Japan"
    level = "bronze"
    is_for_products = True
    group = "geo_japan"
    description = "You made impact in Japan!"

    def decide_if_assigned(self, person):
        for my_product in person.products:
            if my_product.has_country("Japan"):
                self.candidate_badge.add_product(my_product)
                self.assigned = True


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


class practitioner(BadgeAssigner):
    display_name = "Practical Magic"
    level = "bronze"
    is_for_products = False
    group = "poster_types"
    description = "More than 10% of your impact is from practitioners."

    def decide_if_assigned(self, person):
        proportion = proportion_poster_counts_by_type(person, "Practitioners (doctors, other healthcare professionals)")
        if proportion > 0.10:
            self.assigned = True



class media_darling(BadgeAssigner):
    display_name = "Media darling"
    level = "bronze"
    is_for_products = False
    group = "poster_types"
    description = "More than 10% of your impact is from science communicators."

    def decide_if_assigned(self, person):
        proportion = proportion_poster_counts_by_type(person, "Science communicators (journalists, bloggers, editors)")
        if proportion > 0.10:
            self.assigned = True



class channel_everywhere(BadgeAssigner):
    display_name = "Everywhere"
    level = "gold"
    is_for_products = False
    group = "sources_number"
    description = "You have made impact on at least 10 channels."

    def decide_if_assigned(self, person):
        if person.num_sources >= 10:
            self.assigned = True


class channel_star(BadgeAssigner):
    display_name = "Channel star"
    level = "silver"
    is_for_products = False
    group = "sources_number"
    description = "You have made impact on at least 7 channels."

    def decide_if_assigned(self, person):
        if person.num_sources >= 7:
            self.assigned = True


class channel_hit(BadgeAssigner):
    display_name = "Channel hit"
    level = "bronze"
    is_for_products = False
    group = "sources_number"
    description = "You have made impact on at least 5 channels."

    def decide_if_assigned(self, person):
        if person.num_sources >= 5:
            self.assigned = True


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

        self.candidate_badge.support = u"Megafans include: {}".format(u",".join(fans))


class bff(BadgeAssigner):
    display_name = "bff"
    level = "silver"
    is_for_products = True
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

        self.candidate_badge.support = u"BFFs include: {}".format(u",".join(fans))


class school_bus(BadgeAssigner):
    display_name = "School bus"
    level = "bronze"
    is_for_products = True
    group = "impressions"
    description = "The number of twitter impressions your work would a yellow school bus!"

    def decide_if_assigned(self, person):
        if person.impressions >= 56:
            self.assigned = True

class subway_car(BadgeAssigner):
    display_name = "NYC Subway"
    level = "bronze"
    is_for_products = True
    group = "impressions"
    description = "The number of twitter impressions your work would fill a NYC subway car!"

    def decide_if_assigned(self, person):
        if person.impressions >= 200:
            self.assigned = True


class seven_forty_seven(BadgeAssigner):
    display_name = "747"
    level = "silver"
    is_for_products = True
    group = "impressions"
    description = "The number of twitter impressions your work would fill a 747!"

    def decide_if_assigned(self, person):
        if person.impressions >= 400:
            self.assigned = True

class lincoln_center(BadgeAssigner):
    display_name = "Lincoln Center"
    level = "bronze"
    is_for_products = True
    group = "impressions"
    description = "The number of twitter impressions your work would fill Lincoln Center!"

    def decide_if_assigned(self, person):
        if person.impressions >= 2740:
            self.assigned = True

class cruise_ship(BadgeAssigner):
    display_name = "Cruise Ship"
    level = "silver"
    is_for_products = True
    group = "impressions"
    description = "The number of twitter impressions your work would fill a cruise ship!"

    def decide_if_assigned(self, person):
        if person.impressions >= 6296:
            self.assigned = True

class yankee_stadium(BadgeAssigner):
    display_name = "Yankee Stadium"
    level = "gold"
    is_for_products = True
    group = "impressions"
    description = "The number of twitter impressions your work would fill Yankee Stadium!"

    def decide_if_assigned(self, person):
        if person.impressions >= 50000:
            self.assigned = True

class woodstock(BadgeAssigner):
    display_name = "Woodstock"
    level = "gold"
    is_for_products = True
    group = "impressions"
    description = "The number of twitter impressions your work is larger than the number of people who went to Woodstock!"

    def decide_if_assigned(self, person):
        if person.impressions >= 500000:
            self.assigned = True
