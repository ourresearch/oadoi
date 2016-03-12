from models.badge import Badge

def badge_configs_without_functions():
    return all_badge_def


def get_badge_or_None(badge_name, person):
    badge_function = globals()[badge_name]
    my_badge = badge_function(person)
    if my_badge.assigned:
        my_badge.name = badge_name
        my_badge.assign_from_badge_def(**all_badge_defs[badge_name])
        return my_badge
    return None


def big_in_japan(person):
    candidate_badge = Badge(assigned=False)
    for my_product in person.products:
        if my_product.has_country("japan"):
            candidate_badge.assigned = True
            candidate_badge.products[my_product.doi] = True
    return candidate_badge

def megahit(person):
    candidate_badge = Badge(assigned=False)
    for my_product in person.products:
        if my_product.altmetric_score > 100:
            candidate_badge.assigned = True
            candidate_badge.products[my_product.doi] = True
    return candidate_badge

def third_time_charm(person):
    candidate_badge = Badge(assigned=False)
    for my_product in person.products:
        if my_product.altmetric_score > 0:
            candidate_badge.assigned = True
            candidate_badge.products[my_product.doi] = True
    return candidate_badge



all_badge_defs = {
    "big_in_japan": {
        "display_name": "Big in Japan",
        "level": "gold",
        "is_for_products": True,
        "group": "geo_japan",
        "description": "You have 42 products which have more than 3 tweets in Japan",
        "extra_description": None,
        # "function": (lambda person: None)
    },
    "megahit": {
        "display_name": "Twitter famous",
        "level": "silver",
        "is_for_products": False,
        "group": "twitter_impressions",
        "description": "You have made more than 42000 Twitter impressions",
        "extra_description": None,
        # "function": (lambda person: Badge(name="twitter_famous"))
    },
    "third_time_charm": {
        "display_name": "Sleeping beauty",
        "level": "bronze",
        "is_for_products": True,
        "group": "time_sleeping_beauty",
        "description": "You have a product that got popular after a long sleep",
        "extra_description": None,
        # "function": (lambda person: Badge(name="sleeping_beauty", products=dict([(p.doi, True) for p in person.products])))
    }
}
