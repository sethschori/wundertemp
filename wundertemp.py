import json
from random import random
import sys
import time

from bs4 import BeautifulSoup
import docopt
import pytest  # unittest is standard but pytest is more elegant and pythonic
import requests
import vcr

# Global variables

HTTP_ERROR = "The server returned error code {}"
NOT_FOUND_ERROR = "<location not found>"
WUNDERGROUND_URL = "https://www.wunderground.com/cgi-bin/findweather/getForecast"

table_output = False
temp_output = 'b'
sort_output = None
requested_places = []

def parse_place(place):
    # Parse a place and return it in dict format.
    ret = {}
    ret['name'] = place.title()
    try:
        wunder_tuple = get_wunder(place)
        wunder_success = wunder_tuple[0]
        wunder_response = wunder_tuple[1]
        if not wunder_success:
            ret['error'] = wunder_response
            ret['condition'] = None
            ret['temp_f'] = None
        else:
            ret['error'] = None
            ret['condition'] = bs_parse(wunder_response, [{'id':'curCond'},
                                       {'class':'wx-value'}]).lower()
            temp_unit = bs_parse(wunder_response, [{'id':'curTemp'},
                                                   {'class':'wx-unit'}]).lower()
            temp_raw = float(bs_parse(wunder_response, [{'id':'curTemp'},
                                                        {'class':'wx-value'}]))
            if temp_unit.find('f') > -1:
                ret['temp_f'] = temp_raw
            elif temp_unit.find('c') > -1:
                ret['temp_f'] = round(temp_raw * 9 / 5 + 32, 1)
    except:
        ret['error'] = "<unknown error encountered>"
        ret['condition'] = None
        ret['temp_f'] = None
    return ret

def process_args(args):
    # Processes the calling arguments and assigns them to variables. If
    # there are no args, display help and quit.
    if len(args) == 0:
        help_and_quit()
    # If an arg starts with '-' treat it as a flag, otherwise treat it as a
    # string of places. If called with multiple string args, only the last
    # one will be processed, and the rest will be discarded.
    for arg in args:
        if arg[0] == '-':
            process_flag(arg)
        else:
            process_place_string(arg)
    # If no valid requested places, display help and quit.
    if len(requested_places) == 0:
        help_and_quit()

def process_flag(flag_input):
    # Takes a flag string and sets the appropriate flag variable.
    # Strip the leading '-' and lowercase it.
    flag_input = flag_input[1:].lower()
    # Process the flag possibilities.
    global table_output, temp_output, sort_output
    if flag_input == 't' or flag_input == 'table':
        table_output = True
    if flag_input == 'f' or flag_input == 'fahrenheit':
        temp_output = 'f'
    if flag_input == 'c' or flag_input == 'celsius':
        temp_output = 'c'
    if flag_input == 'a' or flag_input == 'alpha':
        sort_output = 'a'
    if flag_input == 'n' or flag_input == 'numeric':
        sort_output = 'n'

def process_place_string(place_string):
    # Takes a single string of comma-separated places, and saves them as a
    # list of comma-separated strings.
    global requested_places
    places_list = place_string.split(',')  # split string to a list
    places_list = [x.strip() for x in places_list]  # remove whitespace
    def f(x): return len(x) > 0
    places_list = list(filter(f, places_list))  # remove blanks
    requested_places = places_list

def get_wunder(place):
    request = requests.get(WUNDERGROUND_URL, params={'query':place})
    test_soup = BeautifulSoup(request.content, "html.parser")
    div_present = test_soup.find("div",attrs={"class":"row city-list"})
    if 200 < request.status_code < 200:
        return False, HTTP_ERROR.format(str(request.status_code))
    # If request contains <div class="row city-list"> it means the place
    # wasn't found.
    elif div_present is None:
        return True, request.content
    # If the place was found, return the html string.
    else:
        return False, NOT_FOUND_ERROR

def bs_parse(wunder_response, list_of_param_objs):
    soup = BeautifulSoup(wunder_response, "html.parser")
    if len(list_of_param_objs) == 1:
        return soup.find(attrs=list_of_param_objs[0]).string
    else:
        return bs_parse(str(soup.find(attrs=list_of_param_objs[0])),
                        list_of_param_objs[1:])

#@vcr.use_cassette("fixtures/vcr_cassettes/wunderground_sf.yaml")
def get_sf():
    return get_wunder("san francisco california")

#@vcr.use_cassette("fixtures/vcr_cassettes/wunderground_tokyo.yaml")
def get_tokyo():
    return get_wunder("tokyo japan")

def test_bs_parse():
    response_sf = get_sf()
    response_tokyo = get_tokyo()
    parsed_sf = bs_parse(response_sf,[{'id':'curCond'},{'class':'wx-value'}])
    assert len(parsed_sf) > 0
    assert re.match([a-z][A-Z], parsed_sf) is not None

def sort_places(places):
    if sort_output == 'a':
        return sorted(places, key=lambda place: place['name'])
    def sort_if_none(elem):
        if elem['temp_f'] is None:
            return 1000
        else:
            return elem['temp_f']
    if sort_output == 'n':
        return sorted(places, key=sort_if_none)
    else:
        return places

def format_table():
    max_place_length = 0
    max_temp_length = 0
    table_string = ""
    for x in requested_places:
        if len(x['name']) > max_place_length:
            max_place_length = len(x['name'])
    for place in requested_places:
        if place['error'] is not None:
            table_string += "{name} {error}\n".format(name=place['name'],
                                                      error=place['error'])
        else:
            if temp_output == 'c':
                temp_to_display = str(round((place['temp_f'] - 32) * 5 / 9, 1)) + ' C'
            elif temp_output == 'f':
                temp_to_display = str(place['temp_f']) + ' F'
            else:
                temp_to_display = "{c} C / {f} F".format(c=str(round((place['temp_f'] - 32) * 5 / 9, 1)), f=str(place['temp_f']))
            if len(temp_to_display) > max_temp_length:
                max_temp_length = len(temp_to_display)
            table_string += '{name}{padding} | {temp} | {condition}\n'.format(
                        name=place['name'],
                        padding=' '*(max_place_length - len(place['name'])),
                        temp=temp_to_display,
                        condition=place['condition'])
    table_string = "="*(max_place_length + max_temp_length + 25) + "\n" + table_string
    table_string = "PLACE{place_padding} | TEMP{temp_padding} | CONDITION\n".format(
                    place_padding=" "*(max_place_length - 5),
                    temp_padding=" "*(max_temp_length -4)) + table_string
    return table_string

def help_and_quit():
    help_message = """
wundertemp scrapes current temperature and condition four cities. It 
either outputs a text-formatted table or returns the data in JSON format.

Command line usage:

python/python3 wundertemp.py [OPTIONS]... [COMMA SEPARATED STRING OF PLACES]

-t, -table          output is a text-formatted table
-c, -celsius        display the temperature(s) in Celsius
-f, -fahrenheit     display the temperature(s) in Fahrenheit
-a, -alpha          sort the output alphabetically
-n, -numeric        sort the output from lowest to highest temperature

If -cf are not specified, both Celsius and Fahrenheit are displayed.
If -an are not specified, the data is returned unsorted.
If -t is not specified, the data is returned in JSON format.

At least one requested place must be specified using the following format:

    "san francisco ca, tokyo japan, new york city ny"

Describe places as specifically as possible, so as to get an exact match.
Separate each place with a comma, and enclose the entire string in quotes.

Here is an example call to wundertemp from the command line:

    python3 wundertemp.py -c -t "paris france, tokyo japan"
"""
    print(help_message)
    sys.exit(0)

from unittest import mock

@mock.patch('sys.exit')
def test_help_and_quit(_, capsys):
    help_and_quit()
    out, err = capsys.readouterr()
    assert len(out) > 0
    assert "wundertemp" in out
    assert pytest.raises(SystemExit)

if __name__ == "__main__":
    # Don't send the 0th argv, because it's the call to wundertemp.
    process_args(sys.argv[1:])
    # Send each element in requested_places to Place with a 1-5 second
    # delay, so that the server doesn't complain about frequent hits.
    #global requested_places
    print("\nChecking wunderground.com...\n")
    for elem_index, elem_string in enumerate(requested_places):
        requested_places[elem_index] = parse_place(elem_string)
        time.sleep(random() + 1)
    requested_places = sort_places(requested_places)
    if table_output == False:
        print(json.dumps(requested_places))
    else:
        print(format_table())
