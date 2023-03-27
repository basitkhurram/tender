from flask import Blueprint, current_app, make_response, request
from flask_cors import cross_origin

from image_finder import get_random_cuisine_image_from_redis as get_images
from yelp_search import find_cuisines, find_eatery
from winner_logic import pick_solo_winner

import base64
import json
import random


send_images_to_www_blueprint = Blueprint("send_images_to_www", __name__)
send_solo_winner_to_www_blueprint = Blueprint("solo_winner_to_www", __name__)


@send_images_to_www_blueprint.route("/send_images")
@cross_origin(origin="localhost", supports_credentials=True,
              headers=["Content-Type", "Authorization"])
def send_cuisine_images_to_www():
    """
    Returns a response containing image URIs.
    """
    # Set the reference to the Redis server.
    redis = current_app.config["redis"]
    # Pull the location from the GET request
    location = request.args.get("location")
    # If a location wasn't provided, it means that
    # we don't need the location. This in turn suggests
    # that we have already sent a selection of cuisines
    # to this user.
    if not location:
        # Pull the cuisines from the cookie that we set.
        cuisines = request.cookies.get("cuisines")
        cuisines = json.loads(cuisines)
        # Select how many images to send at most for each cuisine.
        max_photos_for_cuisine = random.randint(3, 10)
        is_cookie_set = True
    else:
        # The user has sent us a location, so we'll find
        # appropriate cuisines near the location.
        cuisines = find_cuisines(location, redis)
        # We don't need to send too many images just yet.
        # Just find some images and send them to the user,
        # as soon as possible.
        max_photos_for_cuisine = 2
        # We'll need to set a cookie for the selected cuisines.
        is_cookie_set = False

    # We'll map image URIs to cuisine types.
    uris = {}
    for cuisine in cuisines:
        images = get_images(cuisine, redis, number=max_photos_for_cuisine)
        uris[cuisine] = images
    # Send a response containing a mapping of cuisine types to image URIs.
    response = json.dumps(uris)
    response = make_response(response)
    response.mimetype = "application/json"

    # Set the cuisines cookie if it hasn't been set yet.
    if not is_cookie_set:
        cuisines = json.dumps(cuisines)
        response.set_cookie("cuisines", cuisines)
    return response


@send_solo_winner_to_www_blueprint.route("/solo_winner")
@cross_origin(origin="localhost", supports_credentials=True,
              headers=["Content-Type", "Authorization"])
def send_solo_winner_to_www():
    """
    Returns a winning eatery.
    """
    # Pull the location from the GET request.
    location = json.loads(request.args.get("location"))
    # Pull the encoded scores from the GET request.
    scores = request.args.get("scores")
    # Decode and then load the scores.
    scores = base64.b64decode(scores)
    scores = json.loads(scores)
    # Compute the winning cuisine.
    winning_cuisine = pick_solo_winner(scores)
    # Find the winning eatery.
    eatery = find_eatery(winning_cuisine, location)
    # Eateries can belong in multiple categories.
    # We'll set the cuisine type that we used to determine the winner,
    # so that we can tell the user of the winning cuisine.
    eatery["cuisine"] = winning_cuisine

    response = json.dumps(eatery)
    response = make_response(response)
    response.mimetype = "application/json"
    return response
