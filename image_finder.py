import json
import logging
import random
import requests
import yaml


def add_cuisine_images_to_redis(cuisine, redis, image_uris=[]):
    """
    Downloads and adds images of cuisines to redis.

    Args:
        cuisine:    A string representing a cuisine.
        redis:      A reference to the redis server.
        image_uris: A reference to a list, allowing addition
                    of images to an existing list.
    """
    term = cuisine + u" food"
    image_uris = find_images(term, image_uris)
    redis.hset("cuisines", cuisine, json.dumps(image_uris))


def get_random_cuisine_image_from_redis(cuisine, redis):
    """
    Randomly selects an image for the cuisine from redis.

    Args:
        cuisine:    A string representing a cuisine.
        redis:      A reference to the redis server.

    Returns:
        A string representing a URI of an image.
    """
    images = redis.hget("cuisines", cuisine)
    images = json.loads(images)
    image_uri = random.choice(images)
    return image_uri


def find_images(term, image_uris=[]):
    """
    Downloads and returns images for some search query.

    Args:
        term:       A string used for image search query.
        image_uris: A reference to a list, allowing addition
                    of images to an existing list.

    Returns:
        A list of strings representing image URIs.
    """
    # Try to find an image related to the term argument,
    # first using Yummly's API.
    uris = yummly_images(term, image_uris)
    if not uris:
        # If no results from Yummly, try Flickr.
        uris = flickr_images(term, image_uris)
    if not uris:
        # If still no results, try Getty.
        uris = getty_images(term, image_uris)
    return uris


def yummly_images(term, image_uris=[]):
    """
    Downloads and returns images for some search query.

    Args:
        term:       A string used for image search query.
        image_uris: A reference to a list, allowing addition
                    of images to an existing list.

    Returns:
        A list of strings representing image URIs.
    """
    request = YUMMLY_REQUEST + term
    response = requests.get(request, headers=YUMMLY_HEADER)
    if response.status_code == 200:
        response = response.json()
        matches = response["matches"]
        for match in matches:
            if "smallImageUrls" in match:
                uri = match["smallImageUrls"][-1]
                uri = uri[:-len("=s90")]
                image_uris.append(uri)
    return image_uris


def flickr_images(term, image_uris=[]):
    """
    Downloads and returns images for some search query.

    Args:
        term:       A string used for image search query.
        image_uris: A reference to a list, allowing addition
                    of images to an existing list.

    Returns:
        A list of strings representing image URIs.
    """
    request = FLICKR_REQUEST + term
    response = requests.get(request)
    if response.status_code == 200:
        response = response.content
        # Clean the response up and have it ready to parse the JSON
        response = response[len("jsonFlickrApi("): -1]
        response = json.loads(response)
        images = response["photos"]["photo"]
        for image in images:
            # Reassemble the image's URI, based on the response
            uri = "https://farm{0}.staticflickr.com/{1}/{2}_{3}.jpg".format(
                    image["farm"],
                    image["server"],
                    image["id"],
                    image["secret"])
            image_uris.append(uri)
    return image_uris


def getty_images(term, image_uris=[]):
    """
    Downloads and returns images for some search query.

    Args:
        term:       A string used for image search query.
        image_uris: A reference to a list, allowing addition
                    of images to an existing list.

    Returns:
        A list of strings representing image URIs.
    """
    request = GETTY_REQUEST + term
    response = requests.get(request, headers=GETTY_HEADER)
    if response.status_code == 200:
        response = response.json()
        images = response["images"]
        for image in images:
            # Retrieve the image's URI
            uri = image["display_sizes"][0]["uri"].split("?")[0]
            image_uris.append(uri)
    return image_uris


try:
    with open("config", "r") as stream:
        config = yaml.load(stream)

except Exception as error:
    logging.error("Something wrong with the config file, " + str(error))

else:
    GETTY_KEY = config["keys"]["getty"]
    GETTY_HEADER = {"Api-Key": GETTY_KEY}
    GETTY_ENDPOINT = config["endpoints"]["getty"]
    GETTY_REQUEST = "".join([GETTY_ENDPOINT,
                             "?fields=id,title,thumb,referral_destinations",
                             "&sort_order=best",
                             "&phrase="])

    FLICKR_KEY = config["keys"]["flickr"]
    FLICKR_ENDPOINT = config["endpoints"]["flickr"]
    FLICKR_REQUEST = "".join([FLICKR_ENDPOINT,
                             "?method=flickr.photos.search",
                              "&api_key=", FLICKR_KEY,
                              "&tags=food",
                              "&format=json",
                              "&text="])

    YUMMLY_RESULTS = config["limits"]["yummly"]
    YUMMLY_APP_ID = config["yummly"]["app_id"]
    YUMMLY_APP_KEY = config["keys"]["yummly"]
    YUMMLY_HEADER = {"X-Yummly-App-ID": YUMMLY_APP_ID,
                     "X-Yummly-App-Key": YUMMLY_APP_KEY}
    YUMMLY_ENDPOINT = config["endpoints"]["yummly"]
    YUMMLY_REQUEST = "".join([YUMMLY_ENDPOINT,
                              "?requirePictures=true",
                              "&maxResult=", str(YUMMLY_RESULTS),
                              "&q="])
