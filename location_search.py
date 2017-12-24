import logging
import requests
import yaml


def find_similar_locations(location):
    """
    Finds locations that are similar to the provided location string.

    Args:
        location: A string representing a location.

    Returns:
        A list of strings, each string representing a location
        that is in some way similar to the provided location.
    """
    # Use Google's Places' Autocomplete API
    request = PLACES_AUTOCOMPLETE_REQUEST + location
    response = requests.get(request).json()
    locations = response["predictions"]
    for idx in range(len(locations)):
        place_id = locations[idx]["place_id"]
        description = locations[idx]["description"]
        locations[idx] = (place_id, description)
    return locations


def find_country_code(place_id):
    """
    Finds the country code for a location with some place_id.

    Args:
        place_id: A string representing the identifiers that
                  Google Places uses for locations

    Returns:
        A string representing the country code within which
        is the location represented by place_id. The country
        code is in ISO-3166-1 alpha-2 form.
    """
    # Use Google's Places' Details API
    request = PLACES_DETAILS_REQUEST + place_id
    response = requests.get(request).json()
    address_components = response["result"]["address_components"]
    for component in address_components:
        # Surprisingly, Google's API doesn't have a good way to reliably
        # extract the country in which a place_id is within.
        types = component["types"]
        if "country" in types:
            country_code = component["short_name"]
            return country_code
    logging.error("No country code found for place_id:" + place_id)


try:
    with open("config", "r") as stream:
        config = yaml.load(stream)

except Exception as error:
    logging.error("Something wrong with the config file, " + str(error))

else:
    PLACES_KEY = config["keys"]["places"]
    AUTOCOMPLETE_ENDPOINT = config["endpoints"]["places"]["autocomplete"]
    PLACES_AUTOCOMPLETE_REQUEST = "".join([AUTOCOMPLETE_ENDPOINT,
                                           "?key=", PLACES_KEY,
                                           "&types=geocode",
                                           "&input="])
    DETAILS_ENDPOINT = config["endpoints"]["places"]["details"]
    PLACES_DETAILS_REQUEST = "".join([DETAILS_ENDPOINT,
                                      "?key=", PLACES_KEY,
                                      "&placeid="])
