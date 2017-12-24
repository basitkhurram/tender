import random


def pick_solo_winner(scores):
    """
    Picks the winning cuisine, given the user was playing solo.

    Args:
        scores: A dictionary mapping cuisine types to their scores.

    Returns:
        A string representing the winning cuisine.
    """
    # Invert the scores dictionary to find the cuisine with the
    # most votes.
    inverted_scores = {}
    for cuisine, score in scores.items():
        if score not in inverted_scores:
            inverted_scores[score] = set([])
        inverted_scores[score].add(cuisine)
    max_score = max(inverted_scores)
    winners = inverted_scores[max_score]
    winner = random.sample(winners, 1)[0]
    return winner


def pick_party_winner(party_name, scores, redis):
    """
    Picks the winning cuisine, given the user was part of a party.

    Args:
        party_name: A string representing the user's party name.
        scores: 	A list of tuples, with each tuple in the form
                    (cuisine, score), representing the total score
                    for some cuisine. The list is sorted in ascending
                    order of score.

    Returns:
        A string representing the winning cuisine.
    """
    # Find the score held by the highest scoring cuisine(s)
    max_score = scores[-1][-1]
    # Pull the cuisines that have the highest score
    winners = redis.zrangebyscore(u"scores:" + party_name,
                                  max_score, max_score)
    winner = random.sample(winners, 1)[0]
    return winner
