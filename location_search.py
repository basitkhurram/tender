from flask import Blueprint, make_response, request
from flask_cors import cross_origin

import json
import logging
import requests
import yaml


find_similar_locations_blueprint = Blueprint("fsl_blueprint", __name__)


@find_similar_locations_blueprint.route("/location/fsl")
@cross_origin(origin="*",
              headers=['Content-Type', 'Authorization'])
def find_similar_locations_www():
    # Setting a CORS header along with a blueprint seems to force Flask
    # into thinking that app context is required, even when it isn't.
    return find_similar_locations()


def find_similar_locations(location=None):
    """
    Finds locations that are similar to the provided location string.

    Args:
        location: A string representing a location. If location is none,
        assume that the location is being sent in a GET request via the
        find_similar_locations_www method.

    Returns:
        A list of strings, each string representing a location
        that is in some way similar to the provided location.
    """
    www = False
    # If no location was provided, assume called via www
    # In which case, extract the location from query arguments
    if location is None:
        www = True
        location = request.args.get("location")

    # Use Google's Places' Autocomplete API
    api_request = PLACES_AUTOCOMPLETE_REQUEST + location
    response = requests.get(api_request).json()
    locations = response["predictions"]
    for idx in range(len(locations)):
        place_id = locations[idx]["place_id"]
        description = locations[idx]["description"]
        locations[idx] = (place_id, description)

    # TODO: Handle the case when places API returns no matches
    if not locations:
        logging.info("No locations found")
        locations = [("place_id holder", "200 University Avenue, Waterloo")]

    # If communicating via www, send the location in JSON
    if www:
        locations = json.dumps(locations)
        locations = make_response(locations)
        locations.mimetype = "application/json"
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
    api_request = PLACES_DETAILS_REQUEST + place_id
    response = requests.get(api_request).json()
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
