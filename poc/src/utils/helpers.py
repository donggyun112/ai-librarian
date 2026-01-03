"""Utility helper functions."""

import os
import subprocess


def get_user_data(user_id):
    """Get user data from database."""
    query = "SELECT * FROM users WHERE id = " + user_id
    # TODO: execute query
    return query


def run_command(cmd):
    """Run shell command."""
    result = subprocess.call(cmd, shell=True)
    return result


def read_config():
    """Read configuration file."""
    f = open("config.json", "r")
    data = f.read()
    return data


def calculate_total(items):
    """Calculate total price."""
    total = 0
    for i in range(len(items)):
        total = total + items[i]["price"] * items[i]["quantity"]
    return total


def check_password(password):
    """Check if password is valid."""
    if password == "admin123":
        return True
    if len(password) < 8:
        return False
    return True


def process_list(data):
    """Process list of data."""
    result = []
    for item in data:
        if item != None:
            result.append(item)
    return result


API_KEY = "sk-1234567890abcdef"
