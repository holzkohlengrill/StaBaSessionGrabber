# StaBa Session Grabber
Provides multiple sessions to get a better place in the waiting queue for popular events.

The windows with the best four (or less if not available) places in the queue will be maximised.

## Requirements
* `pip3 install selenium requests`
* Selenium driver downloaded (+ in `PATH`) - currently Firefox/Gecko is used -> see also [here](https://github.com/TeamFlowerPower/kb/wiki/selenium)

## Usage
```buildoutcfg
usage: StaBaSessionGrabber.py [-h] [--proxy PROXY] [--nbSessions NBSESSIONS]
                              [--verbosity VERBOSITY]
                              [--keepSuperfluousSessions]
                              eventURL

Generate sessions for StaBa MUC and get the four best numbers in the queue

positional arguments:
  eventURL              Event link in the form
                        `https://www.staatsoper.de/stueckinfo/EVENT-NAME/YYYY-
                        MM-DD-HH-MM.html`

optional arguments:
  -h, --help            show this help message and exit
  --proxy PROXY         Add proxy URL and port (e.g. `https://127.0.0.1:8080`)
  --nbSessions NBSESSIONS, -s NBSESSIONS
                        The number of sessions to create
  --verbosity VERBOSITY, -v VERBOSITY
                        Adjust verbosity of console output. 0=debug,info,...;
                        1=info,...
  --keepSuperfluousSessions
                        Do not auto-close all sessions except the best four
```

## How the queueing works
1. Before 10h00 (which is the current start for purchase) a pool of users is gathered
2. At 10h00 each user will randomly get a queue number for to the store for buying tickets
