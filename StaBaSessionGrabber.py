"""
StaBa Session Grabber
Copyright (C) 2021 Marcel Schmalzl

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>
"""

import sys
import time
import re
import argparse
import timeit
import datetime
# from multiprocessing import Process           # Function currently deactivated

import requests
import lxml
from lxml import html, etree
from pypiscout.SCout_Logger import Logger as sc

from selenium import webdriver


class WaitingSession:
    def __init__(self, queueNb, session):
        self.queueNb = queueNb
        self.session = session


def parse_arguments():
    """
    Parse the arguments
    :return: Arguments
    """
    arguments = argparse.ArgumentParser(prog="StaBaSessionGrabber.py",
                                        description="Generate sessions for StaBa MUC and get the four best numbers in the queue"
                                        )
    arguments.add_argument(
        "--proxy",
        type=str,
        help="Add proxy URL and port (e.g. `https://127.0.0.1:8080`)"
    )
    arguments.add_argument(
        "--nbSessions",
        "-s",
        type=int,
        default=50,
        help="The number of sessions to create"
    )
    arguments.add_argument(
        "--verbosity",
        "-v",
        default=1,
        help="Adjust verbosity of console output. 0=debug,info,...; 1=info,..."
    )
    arguments.add_argument(
        "--keepSuperfluousSessions",
        action='store_true',
        help="Do not auto-close all sessions except the best four"
    )
    arguments.add_argument(
        "eventURL",
        type=str,
        help="Event link in the form `https://www.staatsoper.de/stueckinfo/EVENT-NAME/YYYY-MM-DD-HH-MM.html`"
    )
    return arguments


def process_arguments(arguments):
    """
    Process and check the arguments
    :param arguments: Unparsed arguments
    :return: Parsed and processed arguments
    """
    parsed_args = arguments.parse_args()

    # Check for valid proxy
    if parsed_args.proxy:
        proxy_regex = r"http[s]?://[a-zA-Z0-9.\-]+:\d{4}"          # Matches proxy URL
        pattern = re.compile(proxy_regex)
        match = re.search(pattern, parsed_args.proxy)
        if match:
            result = match.group()
            parsed_args.proxies = {
                "http": result,
                "https": result
            }
        else:
            sc().error(f"Incorrect proxy format (should match the regex: `{proxy_regex}`)")
    else:
        parsed_args.proxies = None


    # Clean-up quoting and whitespaces in URL
    parsed_args.eventURL = parsed_args.eventURL.strip('\"')
    parsed_args.eventURL = parsed_args.eventURL.strip('\'')
    parsed_args.eventURL = parsed_args.eventURL.strip()

    # Check for valid URL
    urlRegex = r"['\"]*http[s]?://www\.staatsoper\.de/stueckinfo/[0-9a-zA-Z\-_]+/\d{4}-\d{2}-\d{2}-\d{2}-\d{2}\.html['\"]*"
    pattern = re.compile(urlRegex)
    match = re.search(pattern, parsed_args.eventURL)
    if not match:
        sc().error(f"Invalid URL provided! Should be in the from {urlRegex}")

    if parsed_args.nbSessions <= 0:
        sc().error("Too less sessions!")
    if parsed_args.nbSessions >= 100:
        sc().warning(f"Session count requested is high ({parsed_args.nbSessions})!")

    # Clean-up intermediate arguments
    del parsed_args.proxy

    return parsed_args


def main():
    """
    Main
    :return: 0
    """
    _args = parse_arguments()
    arguments = process_arguments(_args)

    sc(invVerbosity=arguments.verbosity, actionError=lambda: sys.exit(-10))

    # Start and display time measurement
    TIME_START = timeit.default_timer()
    sc().info("Started processing at", datetime.datetime.now().strftime("%H:%M:%S"))

    # siteEventLink = getEventLink(url)                 # Call without proxy
    siteEventLink = getEventLink(arguments.eventURL, arguments.proxies)


    # Deactivated since we get a `selenium.common.exceptions.TimeoutException: Message: No connection could be made because the target machine actively refused it. (os error 10061)`
    # very quickly.
    # # Start sessions simultaneously:
    # proc = []
    # for i in range(0, 20):
    #     p = Process(target=createSession, args=(siteEventLink,))
    #     p.start()
    #     proc.append(p)
    # for p in proc:
    #     p.join()


    # Create sessions
    sessionsRaw = []
    for sessionCnt in range(0, arguments.nbSessions):
        session = createSession(siteEventLink)
        sc().info(f"Started Selenium session (session {sessionCnt}, URL: {session.current_url})")
        sessionsRaw.append(session) if session is not None else None
        if "seatmap" in session.current_url:
            sc().wwarning("No queue; skipping other iterations!")
            break

    if len(sessionsRaw) < 0:
        sc().info("No sessions created! Exiting...")
        sys.exit(-1)

    # Check if we are still cued and waiting numbers are not yet distributed
    firstSession = sessionsRaw[0]
    foundCountdown = True
    while foundCountdown:
        countdown = checkCountdown(firstSession)
        if countdown is None:
            foundCountdown = False
        else:
            wait = 1
            time.sleep(wait)
            sc().info(f"Waiting for {wait} seconds that; Countdown {countdown}")


    # FIXME: Might be that we have to wait longer (MSc)
    wait = 30
    sc().info(f"Waiting {wait} seconds that page is completely loaded...")
    time.sleep(wait)

    sessions = []
    for session in sessionsRaw:
        sessionObjs = checkUsersAhead(session)
        sessions.append(sessionObjs) if sessionObjs is not None else None

    # Print and sort sessions according to waiting number
    sc().debug("UNsorted sessions:")
    for session in sessions:
        sc().debug(session.queueNb)
    sessions.sort(key=lambda sessionObj: sessionObj.queueNb)   # Sort to get best queue place
    sc().debug("Sorted sessions:")
    for session in sessions:
        sc().debug(session.queueNb)

    NB_BEST_SESSIONS = 4
    assert(NB_BEST_SESSIONS > 1)

    # Raise best four sessions (or less)
    for session in reversed(sessions[0:NB_BEST_SESSIONS]):
        session.session.switch_to.window(session.session.current_window_handle)
        session.session.maximize_window()

    if len(sessions) >= NB_BEST_SESSIONS and (not arguments.keepSuperfluousSessions):
        sc().info("Closing all superfluous sessions...")
        for i, session in enumerate(sessions[NB_BEST_SESSIONS:]):
            sessionNb = i+NB_BEST_SESSIONS
            sc().debug(f" Closing session #{sessionNb}")
            session.session.quit()
    else:
        if arguments.keepSuperfluousSessions:
            sc().wwarning("--keepSuperfluousSessions active. Keeping all superfluous sessions open.")

    # Stop and display time measurement
    TIME_END = timeit.default_timer()
    sc().info("Finished job at:", datetime.datetime.now().strftime("%H:%M:%S"), "(duration: " + "{0:.2f}".format(TIME_END - TIME_START) + "s)")

    return 0


# ##############################################


def createSession(siteEventLink):
    """
    Create Selenium session and keeps it open when I am in a queue
    :param siteEventLink: URL to ticket shop page
    :return: dict(usersAheadOfMe: int, browser: seleniumWebdriverObject)
    """
    # sc().debug(f"Starting Selenium...")
    # Setup page
    browser = webdriver.Firefox()
    browser.get(siteEventLink)

    # wait = 2
    # sc().info("Waiting for", wait, "seconds that page is completely loaded...")
    # time.sleep(wait)
    # sc().info("Current URL", browser.current_url)

    return browser


# Not needed anymore since we use Selenium (FIXME: needs rework to be used in current implementation)
# def getTicketSession(proxyDict, url):
#     session = requests.Session()
#     session.proxies = proxyDict
#     session.trust_env = False  # Potentially not needed
#     # Get website
#     response = session.get(url, proxies=proxyDict)
#     print(response.text)
#     # lxmlWebsiteObj = lxml.html.fromstring(response.text)
#     # Extract cookies which can be copied in the browser to get the session
#     sc().debug("Cookies (get link session):", session.cookies.get_dict())


def getEventLink(url, proxyDict=None):
    session = requests.Session()
    # session.trust_env = False  # Potentially not needed

    # Get website
    response = session.get(url, proxies=proxyDict)
    # print(response.text)
    lxmlWebsiteObj = lxml.html.fromstring(response.text)
    siteInfosSection = extractInfosSection(lxmlWebsiteObj, url)

    siteBuyTicketsSection = extractBuyTicketsClass(siteInfosSection, url)
    siteEventLink = extractEventLink(siteBuyTicketsSection, url)
    sc().info(f"Event link found: {siteEventLink}")
    sc().debug("Cookies (get link session):", session.cookies.get_dict())
    return siteEventLink


def extractInfosSection(lxmlWebsiteObj, url):
    # Extract `infos` section
    contentXPattern = r'//*[@id="infos"]'
    siteInfosSection = lxmlWebsiteObj.xpath(contentXPattern)
    if len(siteInfosSection) == 0:
        sc().error(f"Infos section not found for XPath `{contentXPattern}` | url: {url}")
        sys.exit(-1)
    else:
        resultOutput = lxml.html.tostring(siteInfosSection[0])  # preserves html
        sc().debug(f"Result extractInfosSection: {resultOutput}")
    return siteInfosSection[0]


def extractBuyTicketsClass(siteInfosSection, url):
    # Extract `buyTickets` class
    contentXPattern = r'//*[contains(@class, "buyTickets")]'
    siteBuyTicketsSection = siteInfosSection.xpath(contentXPattern)  # We only want the first result
    if len(siteBuyTicketsSection) == 0:
        sc().error(f"Class `buyTicket` not found for XPath `{contentXPattern}` | url: {url}")
        sys.exit(-1)
    else:
        resultOutput = lxml.html.tostring(siteBuyTicketsSection[0])  # preserves html
        sc().debug(f"Result extractBuyTicketsClass: {resultOutput}")
    return siteBuyTicketsSection[0]


def extractEventLink(siteBuyTicketsSection, url):
    # Extract event link
    contentXPattern = r'.//@href'               # . infront of // means do a local search; otherwise lxml will search the whole html (still not sure where it gets it from since it is a new object)
    siteEventLink = siteBuyTicketsSection.xpath(contentXPattern)  # We only want the first result
    if len(siteEventLink) == 0:
        sc().error(f"Event link not found for XPath `{contentXPattern}` | url: {url}")
        sys.exit(-1)
    else:
        # No idea why this is causing an error
        # From: https://programtalk.com/python-examples/lxml.etree._ElementStringResult/
        #
        # TypeError: Type 'lxml.etree._ElementUnicodeResult' cannot be serialized.
        # TypeError: Type '_ElementStringResult' cannot be serialized.
        if isinstance(siteEventLink[0], etree._ElementStringResult):
            result = siteEventLink[0]
        elif isinstance(siteEventLink[0], etree._ElementUnicodeResult):
            result = siteEventLink[0]
        elif hasattr(siteEventLink[0], 'text'):
            result = siteEventLink[0].text
        else:
            result = etree.tostring(siteEventLink[0])
        sc().debug(f"Result extractEventLink: {result}")
    return result


def checkCountdown(browser):
    waitingXPAttern = r'//*[contains(@class, "beforeElement hasCountdown")]'
    countdown = None
    try:
        usersAheadOfMeTmp = browser.find_element_by_xpath(waitingXPAttern)
        countdownVal = usersAheadOfMeTmp.text
        sc().info(f"Countdown: {countdownVal}")
        countdown = countdownVal if len(usersAheadOfMeTmp) > 0 else None
    except Exception as ex:
        countdown = None
        sc().info("Found no countdown; starting buying sequence")

    return countdown


def checkUsersAhead(browser):
    contentXPattern = r'//*[@id="MainPart_lbUsersInLineAheadOfYou"]'
    waitingSession = None
    try:
        usersAheadOfMeTmp = browser.find_element_by_xpath(contentXPattern)
        usersAheadOfMe = usersAheadOfMeTmp.text
        sc().info(f"Users ahead of me: {usersAheadOfMe}")
        waitingSession = WaitingSession(int(usersAheadOfMe), browser)
    except Exception as ex:
        exName = type(ex).__name__
        sc().warning(f"XPath not found ({exName}) - probably no users ahead of me.")
        waitingSession = WaitingSession(0, browser)
    return waitingSession


if __name__ == '__main__':
    main()
