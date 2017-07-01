"""
This module is used to calculate the score for a node.
"""
BOUNDARY_VALUE = pow(10, 10)


def calculate_score(total_up, total_down):
    """
    Calculate the score given a node dictionary.

    The score is calculated on a scale from 0 till 1, where 0 is the worst and 1 is the best.

    :param total_up: the amount of uploaded data
    :param total_down: the amount of downloaded data
    :return: a number between 0 and 1 which represents the score of the node.
    """
    balance = total_up - total_down
    if balance < -BOUNDARY_VALUE:
        return 0
    elif balance > BOUNDARY_VALUE:
        return 1
    else:
        return (float(balance) + BOUNDARY_VALUE) / (BOUNDARY_VALUE + BOUNDARY_VALUE)
