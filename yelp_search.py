import logging
import random
import requests
import yaml

from location_search import find_country_code


def is_supported_place(place_id):
    """
    Determines whether place_id is within a country supported by Yelp,
    uses SUPPORTED_LOCALES to check for Yelp support.

    Args:
        place_id: A string representing Google's identifier for some place.

    Returns:
        A boolean, indicating whether place_id is within a country
        supported by Yelp.
    """
    country_code = find_country_code(place_id)
    return country_code in SUPPORTED_LOCALES


def find_cuisines(location):
    """
    Finds types of cuisines near the provided location,
    uses RADIUS to determine the search radius.

    Args:
        location: A string representing a location.

    Returns:
        A list of strings representing cuisines found
        near the provided location.
    """
    cuisines = set([])
    # This is the request to get the first page of results
    # from Yelp's API.
    base_request = "".join([YELP_ENDPOINT,
                            "?radius=", str(RADIUS),
                            "&categories=restaurants",
                            "&location=", location])
    # Send an offset in the query to pull more results
    # from Yelp's API.
    offset = 0
    businesses = True
    while businesses and offset < YELP_RESULTS_LIMIT:
        request = "{0}&offset={1}".format(base_request, offset)
        response = requests.get(request,
                                headers=YELP_HEADER).json()
        businesses = response["businesses"]
        for business in businesses:
            for category in business["categories"]:
                cuisine = category["title"]
                if cuisine not in CUISINE_BLACKLIST:
                    cuisines.add(category["title"])
        offset += 20
    return cuisines


def get_updated_cat_map(yelp_cat_map):
    """
    Converts Yelp's category codes for cuisines to
    Yelp's semantic meanings for those codes.

    Args:
        yelp_cat_map: The URL to the JSON file containing Yelp's categories.

    Returns:
        A mapping of Yelp's category codes to their semantic meanings
        (For example, as of writing, "diyfood" maps to "Do-It-Yourself Food").
    """
    raw_mapping = requests.get(yelp_cat_map).json()
    updated_mapping = {}
    for category in raw_mapping:
        alias = category["alias"]
        title = category["title"]
        updated_mapping[title] = alias
    return updated_mapping


def find_eatery(cuisine, location):
    """
    Finds an eatery that serves a certain cuisine near the provided location,
    uses RADIUS to determine search radius.

    Args:
        cuisine:  A string representing some cuisine type.
        location: A string representing some location.

    Returns:
        A string representing some eatery.
    """
    # Search for the cuisine by first determining Yelp's category coding
    # for the cuisine.
    # Check first whether the given cuisine has an encoding in Yelp's
    # categories.json file.
    # (It should have an entry, since the names of the cuisine types
    # are specific to Yelp's own API).
    if cuisine not in YELP_CAT_MAP:
        # Try updating our current mapping of the categories.
        updated_mapping = get_updated_cat_map(YELP_CAT_JSON)
        YELP_CAT_MAP.update(updated_mapping)
        # If updating the mapping didn't help, something's wrong somewhere.
        # Log it as an error, and set the category to pizza for now
        # ... because why not?
        if cuisine not in YELP_CAT_MAP:
            logging.error("Something going on with Yelp's categories.json")
            # When the world is on fire, Pizza will still be there.
            category = "pizza"
        else:
            category = YELP_CAT_MAP[cuisine]
    else:
        category = YELP_CAT_MAP[cuisine]
    request = "".join([YELP_ENDPOINT,
                       "?radius=", str(RADIUS),
                       "&categories=", category,
                       "&location=", location])
    response = requests.get(request,
                            headers=YELP_HEADER).json()
    businesses = response["businesses"]
    eatery = random.choice(businesses)
    return eatery


try:
    with open("config", "r") as stream:
        config = yaml.load(stream)

except Exception as error:
    logging.error("Something wrong with the config file, " + str(error))

else:
    # Maintain a list of some cuisines that make it difficult to find
    # good, relevant images.
    CUISINE_BLACKLIST = set(config["yelp"]["cuisine_blacklist"])

    # Maintain a list of the countries in which Yelp operates.
    SUPPORTED_LOCALES = set(config["yelp"]["supported_locales"])

    # Set the search radius within which to search for cuisines and eateries.
    RADIUS = config["limits"]["radius"]

    # Limit the number of results we want Yelp to send us when we use the API.
    YELP_RESULTS_LIMIT = config["limits"]["yelp"]

    # The URL to the JSON file containing Yelp's categories mapping.
    YELP_CAT_JSON = config["yelp"]["cat_json"]
    YELP_CAT_MAP = get_updated_cat_map(YELP_CAT_JSON)  # Store this on redis?

    YELP_KEY = config["keys"]["yelp"]
    YELP_HEADER = {"Authorization": "Bearer " + YELP_KEY}

    YELP_ENDPOINT = config["endpoints"]["yelp"]
